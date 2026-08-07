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
from typing import Any, Dict, List, Optional

from ..config import Config
from ..database import Database
from .calculator import Component, CourseResult, Group, evaluate_course
from .notion import NotionClient


class GradeSync:
    def __init__(self, db: Optional[Database] = None,
                 notion: Optional[NotionClient] = None):
        self.db = db or Database()
        self.notion = notion or NotionClient(
            token=Config.NOTION_API_KEY,
            courses_db=Config.NOTION_COURSES_DB_ID,
            categories_db=Config.NOTION_CATEGORIES_DB_ID,
            marks_db=Config.NOTION_MARKS_DB_ID,
        )
        self.stats = {"courses": 0, "groups": 0, "components": 0, "snapshots": 0}
        self.problems: List[str] = []

    # ------------------------------------------------------------------ read

    def _load(self, semester: str):
        """Walk Notion's relations into calculator inputs, keyed by course page."""
        courses = [c for c in self.notion.fetch_courses() if not c["archived"]]
        categories = [c for c in self.notion.fetch_categories() if not c["archived"]]
        marks = [m for m in self.notion.fetch_marks() if not m["archived"]]

        wanted = (semester or "").strip().lower()
        in_scope = {
            c["page_id"]: c for c in courses
            if (c["semester"] or "").strip().lower() == wanted
        }
        skipped = len(courses) - len(in_scope)
        if skipped:
            print(f"   {skipped} course(s) from other semesters ignored")

        for course in courses:
            if not course["course"]:
                self.problems.append(
                    f"course row {course['page_id'][:8]} has no Course name")
            elif not course["semester"]:
                self.problems.append(
                    f"{course['course']}: no Semester set, so it never syncs")

        # Marks grouped under their category.
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for mark in marks:
            if not mark["category_page_id"]:
                self.problems.append(
                    f"mark '{mark['item'] or mark['page_id'][:8]}' is not linked "
                    f"to a category")
                continue
            by_category.setdefault(mark["category_page_id"], []).append(mark)

        # Categories grouped under their course.
        grouped: Dict[str, List[Group]] = {}
        for category in categories:
            parent = category["course_page_id"]
            if not parent:
                self.problems.append(
                    f"category '{category['category']}' is not linked to a course")
                continue
            if parent not in in_scope:
                continue

            items = by_category.get(category["page_id"], [])
            grouped.setdefault(parent, []).append(Group(
                key=category["page_id"],
                name=category["category"] or "(unnamed)",
                weight=category["weight"] or 0.0,
                counted=(int(category["counts"])
                         if category["counts"] is not None else None),
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

        return in_scope, grouped

    # ----------------------------------------------------------------- write

    def _course_id_for(self, code: str) -> Optional[str]:
        """Link to the Classroom-synced course when one exists.

        Absence is normal, not an error: a course may be taught offline or
        simply not posted to Classroom, and its grades are typed by hand
        either way.
        """
        rows = self.db.client.table("courses").select("id,course_code").execute().data
        for row in rows:
            if (row.get("course_code") or "").strip().lower() == code.strip().lower():
                return row["id"]
        return None

    def _persist(self, code: str, semester: str, result: CourseResult,
                 counts_by_page: Dict[str, Optional[int]]) -> None:
        course_id = self._course_id_for(code)
        now = datetime.now(timezone.utc).isoformat()

        for group in result.groups:
            self.db.client.table("grade_groups").upsert({
                "course_code": code,
                "course_id": course_id,
                "semester": semester,
                "notion_page_id": group.key,
                "name": group.name,
                "weight": group.weight,
                "counted": counts_by_page.get(group.key),
                "archived": False,
                "updated_at": now,
            }, on_conflict="notion_page_id").execute()
            self.stats["groups"] += 1

            stored = (self.db.client.table("grade_groups").select("id")
                      .eq("notion_page_id", group.key).execute().data)
            if not stored:
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
        """Append a snapshot only when the numbers actually moved.

        Running several times a day would otherwise bury the history in
        identical rows.
        """
        previous = (self.db.client.table("grade_snapshots")
                    .select("earned_weight,graded_weight")
                    .eq("course_code", code)
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
            "percentage": round(result.percentage, 2) if result.percentage else None,
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

    def _push(self, course_page_id: str, result: CourseResult) -> None:
        notes: List[str] = list(result.warnings)

        for group in result.groups:
            notes.extend(group.warnings)
            dropped = [c.name for c in group.components
                       if not c.is_counted and c.score is not None]
            self.notion.update_category_row(
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

        self.notion.update_course_row(
            page_id=course_page_id,
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
            return self.stats

        in_scope, grouped = self._load(semester)
        print(f"Courses in {semester}: {len(in_scope)}")
        print()

        for page_id, course in sorted(in_scope.items(),
                                      key=lambda kv: kv[1]["course"] or ""):
            code = (course["course"] or "").strip()
            if not code:
                continue

            groups = grouped.get(page_id, [])
            counts_by_page = {g.key: g.counted for g in groups}

            result = evaluate_course(code, groups)
            self._persist(code, semester, result, counts_by_page)
            self._push(page_id, result)
            self.stats["courses"] += 1

            flag = f"   [{'; '.join(result.warnings)}]" if result.warnings else ""
            print(f"  {code:10} {len(groups):2} categories   "
                  f"{result.marks:>18}{flag}")

        if self.problems:
            print()
            print("Problems needing attention in Notion:")
            for problem in self.problems:
                print(f"  - {problem}")

        return self.stats
