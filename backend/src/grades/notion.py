"""
Notion API wrapper for the grade tracker.

Thin on purpose: it reads the three databases into plain dictionaries and
writes computed values back. No grade logic lives here -- that is
calculator.py, which stays free of I/O so it can be tested directly.

The databases form a drill-down, linked by relations rather than by matching
text: a course owns categories, a category owns marks. Relations mean a
renamed course cannot orphan its categories.
"""

import time
from typing import Any, Dict, List, Optional

import requests

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"

# Notion allows roughly three requests a second. Writes are issued one at a
# time with this gap rather than in a burst, because a 429 part-way through
# would leave some pages updated and others stale.
_REQUEST_GAP = 0.34


class NotionError(RuntimeError):
    pass


def _plain_text(prop: Optional[Dict[str, Any]]) -> Optional[str]:
    """Flatten a title or rich_text property to a string."""
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


def _first_relation(prop: Optional[Dict[str, Any]]) -> Optional[str]:
    if not prop or prop.get("type") != "relation":
        return None
    items = prop.get("relation") or []
    return items[0]["id"] if items else None


def _rich(value: Optional[str]) -> List[Dict[str, Any]]:
    """Build a rich_text payload, tolerating None and Notion's 2000-char cap."""
    if not value:
        return []
    return [{"type": "text", "text": {"content": str(value)[:2000]}}]


class NotionClient:
    def __init__(self, token: str, courses_db: str, categories_db: str,
                 marks_db: str):
        self.courses_db = courses_db
        self.categories_db = categories_db
        self.marks_db = marks_db
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------- transport

    def _request(self, method: str, path: str, payload=None, attempts: int = 4):
        """Issue a request, retrying rate limits and transient failures.

        Only 429 and 5xx are retried. A 400 or 404 means a bad payload or a
        page the integration cannot see, and retrying only delays the error.
        """
        last = None
        for attempt in range(attempts):
            response = self._session.request(
                method, f"{API}{path}", json=payload, timeout=30
            )
            if response.ok:
                return response.json()

            last = f"{response.status_code}: {response.text[:300]}"
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 2 ** attempt)))
                continue
            if 500 <= response.status_code < 600:
                time.sleep(2 ** attempt)
                continue
            break

        raise NotionError(f"{method} {path} -> {last}")

    def _query_all(self, database_id: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        cursor = None
        while True:
            payload: Dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            body = self._request("POST", f"/databases/{database_id}/query", payload)
            rows.extend(body.get("results", []))
            if not body.get("has_more"):
                return rows
            cursor = body.get("next_cursor")

    # ----------------------------------------------------------------- reads

    def fetch_courses(self) -> List[Dict[str, Any]]:
        out = []
        for page in self._query_all(self.courses_db):
            props = page.get("properties", {})
            out.append({
                "page_id": page["id"],
                "course": _plain_text(props.get("Course")),
                "semester": _plain_text(props.get("Semester")),
                "archived": bool(page.get("archived")),
            })
        return out

    def fetch_categories(self) -> List[Dict[str, Any]]:
        out = []
        for page in self._query_all(self.categories_db):
            props = page.get("properties", {})
            out.append({
                "page_id": page["id"],
                "category": _plain_text(props.get("Category")),
                "course_page_id": _first_relation(props.get("Course")),
                "weight": _number(props.get("Weight")),
                # Blank Counts means every component counts; kept as None so
                # the calculator can tell "all of them" from "exactly one".
                "counts": _number(props.get("Counts")),
                "archived": bool(page.get("archived")),
            })
        return out

    def fetch_marks(self) -> List[Dict[str, Any]]:
        out = []
        for page in self._query_all(self.marks_db):
            props = page.get("properties", {})
            out.append({
                "page_id": page["id"],
                "item": _plain_text(props.get("Item")),
                "category_page_id": _first_relation(props.get("Category")),
                # None means not marked yet, which is not the same as zero.
                "score": _number(props.get("Score")),
                "max_score": _number(props.get("Max")),
                "archived": bool(page.get("archived")),
            })
        return out

    # ---------------------------------------------------------------- writes

    def update_course_row(self, page_id: str, marks: str,
                          percent: Optional[float], notes: str,
                          updated_iso: str) -> None:
        """Percent is stored as a fraction; the property uses Notion's
        percent format, which multiplies by 100 for display."""
        self._request("PATCH", f"/pages/{page_id}", {
            "properties": {
                "Marks": {"rich_text": _rich(marks)},
                "Percent": {"number": round(percent / 100.0, 4)
                            if percent is not None else None},
                "Updated": {"date": {"start": updated_iso}},
                "Notes": {"rich_text": _rich(notes)},
            }
        })
        time.sleep(_REQUEST_GAP)

    def update_category_row(self, page_id: str, marks: str, score: str,
                            dropped: str) -> None:
        self._request("PATCH", f"/pages/{page_id}", {
            "properties": {
                "Marks": {"rich_text": _rich(marks)},
                "Score": {"rich_text": _rich(score)},
                "Dropped": {"rich_text": _rich(dropped)},
            }
        })
        time.sleep(_REQUEST_GAP)

    def update_marks_row(self, page_id: str, counted: bool,
                         effective_weight: Optional[float]) -> None:
        self._request("PATCH", f"/pages/{page_id}", {
            "properties": {
                "Counted": {"checkbox": bool(counted)},
                "Weight": {"number": round(effective_weight, 4)
                           if effective_weight else None},
            }
        })
        time.sleep(_REQUEST_GAP)

    # -------------------------------------------------------------- creation
    # Used by the seeding script, not by the sync itself.

    def create_course_row(self, course: str, semester: str) -> str:
        body = self._request("POST", "/pages", {
            "parent": {"database_id": self.courses_db},
            "properties": {
                "Course": {"title": _rich(course)},
                "Semester": {"rich_text": _rich(semester)},
            },
        })
        time.sleep(_REQUEST_GAP)
        return body["id"]

    def create_category_row(self, course_page_id: str, category: str,
                            weight: float, counts: Optional[int]) -> str:
        body = self._request("POST", "/pages", {
            "parent": {"database_id": self.categories_db},
            "properties": {
                "Category": {"title": _rich(category)},
                "Course": {"relation": [{"id": course_page_id}]},
                "Weight": {"number": weight},
                "Counts": {"number": counts},
            },
        })
        time.sleep(_REQUEST_GAP)
        return body["id"]
