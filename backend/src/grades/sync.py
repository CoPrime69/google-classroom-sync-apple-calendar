"""
Grade sync orchestration.

Moves data between Notion and Supabase and asks calculator.py for the
arithmetic. Deliberately holds no grade rules of its own.

Direction of travel, one writer per field:
    Notion   -> Supabase   weights, counts, scores, maxima (what you type)
    Supabase -> Notion     standings, dropped flags, effective weights
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..config import Config
from ..database import Database
from .calculator import Component, CourseResult, Group, evaluate_course
from .notion import (COMPONENTS_DB_TITLE, MARKS_DB_TITLE, COMPONENT_PROPERTIES,
                     MARK_PROPERTIES, NotionClient)


def _key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


class GradeSync:
    def __init__(self, db: Optional[Database] = None,
                 notion: Optional[NotionClient] = None):
        self.db = db or Database()
        self.notion = notion or NotionClient(
            token=Config.NOTION_API_KEY,
            courses_db=Config.NOTION_COURSES_DB_ID,
            progress_db=Config.NOTION_PROGRESS_DB_ID,
        )
        self.stats = {"courses": 0, "groups": 0, "components": 0, "snapshots": 0}
        self.problems: List[str] = []
        self.failures = 0

    # ------------------------------------------------------------------ read

    def _groups_for(self, course_code: str, page_id: str) -> List[Group]:
        """Read one course's own Components and Marks tables."""
        children = self.notion.child_databases(page_id)

        components_db = children.get(COMPONENTS_DB_TITLE)
        if not components_db:
            # Self-heal: a course added by hand in Notion has no child tables
            # until the job makes them, so it is created rather than reported.
            components_db = self.notion.ensure_child_db(
                page_id, COMPONENTS_DB_TITLE, COMPONENT_PROPERTIES,
                "Components for this course. Counts = how many contribute; "
                "leave blank when all of them do.")
            print(f"     created missing {COMPONENTS_DB_TITLE} table")

        marks_db = children.get(MARKS_DB_TITLE)
        if not marks_db:
            marks_db = self.notion.ensure_child_db(
                page_id, MARKS_DB_TITLE, MARK_PROPERTIES,
                "Marks for this course. Component must match a row in the "
                "Components table above. Leave Score empty until marked.")
            print(f"     created missing {MARKS_DB_TITLE} table")

        components = self.notion.fetch_components(components_db)
        marks = self.notion.fetch_marks(marks_db)

        by_component: Dict[str, List[dict]] = {}
        # Nameless component rows are reported separately below. Including
        # them here would put "" in `known`, so a mark with a blank Component
        # would look matched and then be dropped without any warning.
        known = {_key(c["component"]) for c in components if c["component"]}
        for mark in marks:
            name = _key(mark["component"])
            if name not in known:
                self.problems.append(
                    f"{course_code}: mark '{mark['item'] or 'unnamed'}' names "
                    f"component '{mark['component']}', which is not in this "
                    f"course's Components table")
                continue
            by_component.setdefault(name, []).append(mark)

        groups = []
        for component in components:
            if not component["component"]:
                self.problems.append(
                    f"{course_code}: a component row has no name")
                continue
            # pop, not get: two rows with the same name would otherwise each
            # take the same marks and double-count the whole group.
            items = by_component.pop(_key(component["component"]), [])
            groups.append(Group(
                key=component["page_id"],
                name=component["component"],
                weight=component["weight"] or 0.0,
                counted=(int(component["counts"])
                         if component["counts"] is not None else None),
                components=tuple(
                    Component(
                        key=m["page_id"],
                        name=m["item"] or "(unnamed)",
                        score=m["score"],
                        max_score=m["max_score"],
                    )
                    for m in items
                ),
            ))
        return groups

    # ----------------------------------------------------------------- write

    def _course_ids(self) -> Dict[str, str]:
        """Map course_code -> courses.id, built once per run.

        Linking to the Classroom-synced course is a convenience; absence is
        normal, because a course may be taught offline or simply not posted to
        Classroom, and its grades are typed by hand either way.
        """
        rows = self.db.client.table("courses").select("id,course_code").execute().data
        return {_key(r["course_code"]): r["id"] for r in rows if r.get("course_code")}

    def _persist(self, code: str, semester: str, result: CourseResult,
                 counts_by_page: Dict[str, Optional[int]],
                 course_id: Optional[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()

        for group in result.groups:
            stored = self.db.client.table("grade_groups").upsert({
                "course_code": code,
                "course_id": course_id,
                "semester": semester,
                "notion_page_id": group.key,
                "name": group.name,
                "weight": group.weight,
                "counted": counts_by_page.get(group.key),
                "archived": False,
                "updated_at": now,
            }, on_conflict="notion_page_id").execute().data
            self.stats["groups"] += 1

            # postgrest returns the upserted row by default, so the id is
            # already here; selecting it again was a wasted round-trip.
            if not stored:
                self.problems.append(
                    f"{code}: could not persist component {group.name!r}")
                continue

            for component in group.components:
                self.db.client.table("grade_components").upsert({
                    "group_id": stored[0]["id"],
                    "notion_page_id": component.key,
                    "name": component.name,
                    "score": component.score,
                    "max_score": component.max_score,
                    "is_dropped": not component.is_counted,
                    "effective_weight": component.effective_weight,
                    "archived": False,
                    "updated_at": now,
                }, on_conflict="notion_page_id").execute()
                self.stats["components"] += 1

        self._snapshot(code, course_id, semester, result)

    def _snapshot(self, code: str, course_id: Optional[str], semester: str,
                  result: CourseResult) -> None:
        """Append only when the numbers moved, so a repeatedly scheduled job
        does not bury the history in identical rows."""
        previous = (self.db.client.table("grade_snapshots")
                    .select("earned_weight,graded_weight")
                    .eq("course_code", code).eq("semester", semester)
                    .order("id", desc=True).limit(1).execute().data)

        if previous:
            unchanged = (
                abs(float(previous[0]["earned_weight"]) - result.earned_weight) < 1e-6
                and abs(float(previous[0]["graded_weight"]) - result.graded_weight) < 1e-6
            )
            if unchanged:
                return

        self.db.client.table("grade_snapshots").insert({
            "course_code": code,
            "course_id": course_id,
            "semester": semester,
            "earned_weight": round(result.earned_weight, 4),
            "graded_weight": round(result.graded_weight, 4),
            # A genuine 0% must not be stored as NULL, which would be
            # indistinguishable from "nothing graded yet".
            "percentage": (round(result.percentage, 2)
                           if result.percentage is not None else None),
            "detail": json.loads(json.dumps({
                "groups": [
                    {
                        "name": g.name,
                        "weight": g.weight,
                        "earned": round(g.earned_weight, 4),
                        "graded": round(g.graded_weight, 4),
                        "rollup": g.rollup,
                        "dropped": [c.name for c in g.components
                                    if not c.is_counted and c.score is not None],
                    }
                    for g in result.groups
                ],
                "warnings": list(result.warnings),
            })),
        }).execute()
        self.stats["snapshots"] += 1

    def _push(self, result: CourseResult, semester: str,
              progress_pages: Dict[str, str]) -> None:
        notes: List[str] = list(result.warnings)

        for group in result.groups:
            notes.extend(group.warnings)
            dropped = [c.name for c in group.components
                       if not c.is_counted and c.score is not None]
            self.notion.update_component_row(
                page_id=group.key,
                marks=group.rollup if group.graded_weight else "",
                score=(f"{group.earned_weight:.2f} / {group.graded_weight:.2f}"
                       if group.graded_weight else ""),
                dropped=", ".join(dropped),
            )
            for component in group.components:
                self.notion.update_marks_row(
                    page_id=component.key,
                    counted=component.is_counted,
                    effective_weight=component.effective_weight,
                )

        progress_pages[result.course.strip().lower()] = self.notion.upsert_progress_row(
            existing=progress_pages,
            course=result.course,
            semester=semester,
            marks=result.marks,
            percent=result.percentage,
            notes="; ".join(notes),
            updated_iso=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------- run

    def run(self) -> Dict[str, int]:
        semester = self.db.get_current_semester()
        print()
        print(f"Current semester: {semester or '(unset)'}")
        if not semester:
            print("   Set settings.current_semester before syncing grades.")
            self.stats["failures"] = self.failures
            return self.stats

        courses = self.notion.fetch_courses()
        in_scope = [c for c in courses if _key(c["semester"]) == _key(semester)]

        skipped = len(courses) - len(in_scope)
        if skipped:
            print(f"   {skipped} course(s) from other semesters ignored")

        for course in courses:
            if not course["course"]:
                self.problems.append(
                    f"course row {course['page_id'][:8]} has no name")
            elif not course["semester"]:
                self.problems.append(
                    f"{course['course']}: no Semester set, so it never syncs")

        progress_pages = self.notion.fetch_progress()
        print(f"Courses in {semester}: {len(in_scope)}")
        print()

        course_ids = self._course_ids()

        for course in sorted(in_scope, key=lambda c: c["course"] or ""):
            code = (course["course"] or "").strip()
            if not code:
                continue

            # Per-course isolation. Without it a single unreadable course --
            # a page unshared from the integration, say -- aborted the whole
            # run, so later courses never synced and every problem collected
            # so far was discarded with the loop.
            try:
                groups = self._groups_for(code, course["page_id"])
                counts_by_page = {g.key: g.counted for g in groups}

                result = evaluate_course(code, groups)
                self._persist(code, semester, result, counts_by_page,
                              course_ids.get(_key(code)))
                self._push(result, semester, progress_pages)
                self.stats["courses"] += 1

                flag = f"   [{'; '.join(result.warnings)}]" if result.warnings else ""
                print(f"  {code:10} {len(groups):2} components   "
                      f"{result.marks:>18}{flag}")
            except Exception as exc:
                self.failures += 1
                self.problems.append(f"{code}: sync failed, skipped ({exc})")
                print(f"  {code:10} FAILED - {exc}")

        if self.problems:
            print()
            print("Problems needing attention in Notion:")
            for problem in self.problems:
                print(f"  - {problem}")

        self.stats["failures"] = self.failures
        return self.stats
