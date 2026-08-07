"""
Notion API wrapper for the grade tracker.

Thin on purpose: it reads Notion into plain dictionaries and writes computed
values back. No grade logic lives here -- that is calculator.py, which stays
free of I/O so it can be tested directly.

Layout: one top-level Courses database, and inside each course's page two
child databases of its own.

    Courses (database)
      CSL7360  (row -> page)
        Components (child database)   Quizzes  15%  counts 5
        Marks      (child database)   Quiz 1   8/10

Components live under their course rather than in one shared table so that
opening a course shows only its own. The cost is that Marks must also be per
course: a Notion relation targets exactly one database, so a single shared
Marks table could not point at four separate Components tables. Within a
course, a mark names its component as text, and an unmatched name is reported
rather than silently ignored.
"""

import time
from typing import Any, Dict, List, Optional

import requests

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"

COMPONENTS_DB_TITLE = "Components"
MARKS_DB_TITLE = "Marks"

# Notion allows roughly three requests a second. Writes go one at a time with
# this gap rather than in a burst, because a 429 part-way through would leave
# some pages updated and others stale.
_REQUEST_GAP = 0.34


class NotionError(RuntimeError):
    pass


def _retry_after(header: Optional[str], fallback: float) -> float:
    """Seconds to wait after a 429.

    RFC 7231 also permits an HTTP-date, and a CDN in front of Notion can send
    one. float() on that raises ValueError, which is not a NotionError and so
    escaped every caller's error contract. Capped so a large value cannot idle
    a paid runner for an hour.
    """
    try:
        seconds = float(header)
    except (TypeError, ValueError):
        seconds = fallback
    return max(0.0, min(seconds, 30.0))


def _plain_text(prop: Optional[Dict[str, Any]]) -> Optional[str]:
    if not prop:
        return None
    kind = prop.get("type")
    if kind not in ("title", "rich_text"):
        return None
    text = "".join(part.get("plain_text", "") for part in prop.get(kind) or [])
    return text.strip() or None


def _number(prop: Optional[Dict[str, Any]]) -> Optional[float]:
    if not prop or prop.get("type") != "number":
        return None
    return prop.get("number")


def _rich(value: Optional[str]) -> List[Dict[str, Any]]:
    if not value:
        return []
    return [{"type": "text", "text": {"content": str(value)[:2000]}}]


COMPONENT_PROPERTIES = {
    "Component": {"title": {}},
    "Weight":   {"number": {"format": "number"}},
    "Counts":   {"number": {"format": "number"}},
    # Written by the job.
    "Marks":    {"rich_text": {}},   # raw rollup, e.g. 52/70
    "Score":    {"rich_text": {}},   # weighted, e.g. 10.80 / 15.00
    "Dropped":  {"rich_text": {}},
}

MARK_PROPERTIES = {
    "Item":     {"title": {}},
    "Component": {"rich_text": {}},
    "Score":    {"number": {"format": "number"}},
    "Max":      {"number": {"format": "number"}},
    # Written by the job.
    "Counted":  {"checkbox": {}},
    "Weight":   {"number": {"format": "number"}},
}


class NotionClient:
    def __init__(self, token: str, courses_db: str, progress_db: str):
        self.courses_db = courses_db
        self.progress_db = progress_db
        self._last_write = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------- transport

    def _request(self, method: str, path: str, payload=None, params=None,
                 attempts: int = 4):
        """Issue a request, retrying transient failures.

        Retries 429, 5xx and network errors. A 400 or 404 means a bad payload
        or a page the integration cannot see; retrying those only delays the
        error. Every failure leaves as NotionError, so callers have a single
        exception type to handle.
        """
        last = None

        for attempt in range(attempts):
            delay = float(2 ** attempt)
            try:
                response = self._session.request(
                    method, f"{API}{path}", json=payload, params=params,
                    timeout=30,
                )
            except requests.RequestException as exc:
                # A dropped connection across a few hundred requests is likelier
                # than a 500, and was previously the one case with no retry.
                last = f"network error: {exc}"
            else:
                if response.status_code < 300:
                    self._throttle(method)
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise NotionError(
                            f"{method} {path} -> non-JSON response: {exc}")

                last = f"{response.status_code}: {response.text[:300]}"
                if response.status_code == 429:
                    delay = _retry_after(response.headers.get("Retry-After"), delay)
                elif not 500 <= response.status_code < 600:
                    break

            # Sleeping on the final attempt buys nothing; it raises next.
            if attempt < attempts - 1:
                time.sleep(delay)

        raise NotionError(f"{method} {path} -> {last}")

    def _throttle(self, method: str) -> None:
        """Keep writes under Notion's roughly three requests a second.

        Applied centrally rather than at the end of every write method, where
        it was seven duplicated lines and easy to omit on the next one. The
        request itself already consumed part of the interval, so only the
        remainder is slept.
        """
        if method == "GET":
            return
        remaining = _REQUEST_GAP - (time.monotonic() - self._last_write)
        if remaining > 0:
            time.sleep(remaining)
        self._last_write = time.monotonic()

    def _query_all(self, database_id: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        cursor = None
        while True:
            payload: Dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            body = self._request("POST", f"/databases/{database_id}/query", payload)
            rows.extend(body.get("results", []))
            # Trusting has_more with a null cursor would re-request page one
            # forever, appending duplicates until the runner ran out of memory.
            cursor = body.get("next_cursor")
            if not cursor:
                return rows

    def child_databases(self, page_id: str) -> Dict[str, str]:
        """Map child-database title -> id for one page."""
        found: Dict[str, str] = {}
        cursor = None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            body = self._request("GET", f"/blocks/{page_id}/children", params=params)
            for block in body.get("results", []):
                if block.get("type") == "child_database":
                    found[block["child_database"]["title"]] = block["id"]
            cursor = body.get("next_cursor")
            if not cursor:
                return found

    # ----------------------------------------------------------------- reads

    def fetch_courses(self) -> List[Dict[str, Any]]:
        out = []
        for page in self._query_all(self.courses_db):
            props = page.get("properties", {})
            out.append({
                "page_id": page["id"],
                "course": _plain_text(props.get("Course")),
                "semester": _plain_text(props.get("Semester")),
            })
        return out

    def fetch_components(self, database_id: str) -> List[Dict[str, Any]]:
        out = []
        for page in self._query_all(database_id):
            props = page.get("properties", {})
            out.append({
                "page_id": page["id"],
                "component": _plain_text(props.get("Component")),
                "weight": _number(props.get("Weight")),
                # Blank Counts means every component counts; kept as None so
                # the calculator can tell "all of them" from "exactly one".
                "counts": _number(props.get("Counts")),
            })
        return out

    def fetch_marks(self, database_id: str) -> List[Dict[str, Any]]:
        out = []
        for page in self._query_all(database_id):
            props = page.get("properties", {})
            out.append({
                "page_id": page["id"],
                "item": _plain_text(props.get("Item")),
                "component": _plain_text(props.get("Component")),
                # None means not marked yet, which is not the same as zero.
                "score": _number(props.get("Score")),
                "max_score": _number(props.get("Max")),
            })
        return out

    # ---------------------------------------------------------------- writes

    def fetch_progress(self) -> Dict[str, str]:
        """Existing Progress rows as course code -> page id, for upserting."""
        found = {}
        for page in self._query_all(self.progress_db):
            code = _plain_text(page.get("properties", {}).get("Course"))
            if code:
                found[code.strip().lower()] = page["id"]
        return found

    def upsert_progress_row(self, existing: Dict[str, str], course: str,
                            semester: str, marks: str, percent: Optional[float],
                            notes: str, updated_iso: str) -> str:
        """Write one course's overall standing to the Progress page.

        `percent` arrives on a 0-100 scale and is stored as a fraction,
        because the property uses Notion's percent format, which multiplies by
        100 again for display.

        Returns the page id rather than writing into the caller's dict, which
        was a mutation invisible at the call site.
        """
        properties = {
            "Course": {"title": _rich(course)},
            "Semester": {"rich_text": _rich(semester)},
            "Marks": {"rich_text": _rich(marks)},
            "Percent": {"number": round(percent / 100.0, 4)
                        if percent is not None else None},
            "Updated": {"date": {"start": updated_iso}},
            "Notes": {"rich_text": _rich(notes)},
        }
        page_id = existing.get(course.strip().lower())
        if page_id:
            self._request("PATCH", f"/pages/{page_id}", {"properties": properties})
            return page_id

        body = self._request("POST", "/pages", {
            "parent": {"database_id": self.progress_db},
            "properties": properties,
        })
        return body["id"]

    def update_component_row(self, page_id: str, marks: str, score: str,
                            dropped: str) -> None:
        self._request("PATCH", f"/pages/{page_id}", {
            "properties": {
                "Marks": {"rich_text": _rich(marks)},
                "Score": {"rich_text": _rich(score)},
                "Dropped": {"rich_text": _rich(dropped)},
            }
        })

    def update_marks_row(self, page_id: str, counted: bool,
                         effective_weight: Optional[float]) -> None:
        self._request("PATCH", f"/pages/{page_id}", {
            "properties": {
                "Counted": {"checkbox": bool(counted)},
                # A dropped component has weight 0.0. Writing None made it
                # indistinguishable from a row the job had never touched.
                "Weight": {"number": round(effective_weight, 4)
                           if effective_weight is not None else None},
            }
        })

    # -------------------------------------------------------------- creation

    def create_course(self, course: str, semester: str) -> Dict[str, str]:
        """Create a course row and the two child databases on its page."""
        page = self._request("POST", "/pages", {
            "parent": {"database_id": self.courses_db},
            "properties": {
                "Course": {"title": _rich(course)},
                "Semester": {"rich_text": _rich(semester)},
            },
        })
        page_id = page["id"]
        return {
            "page_id": page_id,
            COMPONENTS_DB_TITLE: self.ensure_child_db(
                page_id, COMPONENTS_DB_TITLE, COMPONENT_PROPERTIES,
                "Components for this course. Counts = how many contribute; "
                "leave blank when all of them do."),
            MARKS_DB_TITLE: self.ensure_child_db(
                page_id, MARKS_DB_TITLE, MARK_PROPERTIES,
                "Marks for this course. Component must match a row in the "
                "Components table above. Leave Score empty until marked."),
        }

    def ensure_child_db(self, page_id: str, title: str,
                        properties: Dict[str, Any], description: str) -> str:
        """Create a child database on a page, or return the existing one."""
        existing = self.child_databases(page_id)
        if title in existing:
            return existing[title]

        body = self._request("POST", "/databases", {
            "parent": {"type": "page_id", "page_id": page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "description": [{"type": "text", "text": {"content": description}}],
            "properties": properties,
        })
        return body["id"]

    def create_component(self, database_id: str, component: str, weight: float,
                        counts: Optional[int]) -> str:
        body = self._request("POST", "/pages", {
            "parent": {"database_id": database_id},
            "properties": {
                "Component": {"title": _rich(component)},
                "Weight": {"number": weight},
                "Counts": {"number": counts},
            },
        })
        return body["id"]

    def create_mark(self, database_id: str, item: str, component: str,
                    score: Optional[float], max_score: Optional[float]) -> str:
        body = self._request("POST", "/pages", {
            "parent": {"database_id": database_id},
            "properties": {
                "Item": {"title": _rich(item)},
                "Component": {"rich_text": _rich(component)},
                "Score": {"number": score},
                "Max": {"number": max_score},
            },
        })
        return body["id"]
