#!/usr/bin/env python3
"""
Create the three Notion databases the grade tracker reads and writes.

Structure is a drill-down: a course owns categories, a category owns marks.

    Courses      CSL7360 · 7th sem · 10.80/15.00 · 72%
      Categories   Quizzes · 15% · counts 5 · 52/70 · dropped Quiz 5
        Marks        Quiz 1 · 8/10 · counted · w 3.00

Opening a course shows its categories; opening a category shows its marks.
Semester lives on the course row only, so it is set once rather than repeated
on every category.

    python scripts/bootstrap_notion.py               # create/verify
    python scripts/bootstrap_notion.py --recreate    # archive and rebuild
    python scripts/bootstrap_notion.py --print-ids

The databases persist across semesters. A new semester means new rows, not a
rebuild.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from dotenv import dotenv_values

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"

PARENT_PAGE_ID = "3b57b66497ed803ea58ef30a3c478779"

COURSES_TITLE = "Courses"
CATEGORIES_TITLE = "Categories"
MARKS_TITLE = "Marks"

# Created parents-first: each relation needs its target to exist already.
ORDER = [COURSES_TITLE, CATEGORIES_TITLE, MARKS_TITLE]


def _headers():
    env = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env"))
    token = (env.get("NOTION_API_KEY") or os.getenv("NOTION_API_KEY") or "").strip()
    if not token:
        raise SystemExit("NOTION_API_KEY is not set in backend/.env")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _post(path, payload, headers):
    r = requests.post(f"{API}{path}", json=payload, headers=headers, timeout=30)
    if not r.ok:
        raise SystemExit(f"POST {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


def find_existing(headers):
    """Map title -> database id for databases under the parent page."""
    found = {}
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(f"{API}/blocks/{PARENT_PAGE_ID}/children",
                         params=params, headers=headers, timeout=30)
        if not r.ok:
            raise SystemExit(f"listing children -> {r.status_code}: {r.text[:300]}")
        body = r.json()
        for block in body.get("results", []):
            if block.get("type") == "child_database":
                found[block["child_database"]["title"]] = block["id"]
        if not body.get("has_more"):
            return found
        cursor = body.get("next_cursor")


def archive_database(db_id, headers):
    r = requests.patch(f"{API}/databases/{db_id}", json={"archived": True},
                       headers=headers, timeout=30)
    if not r.ok:
        raise SystemExit(f"archiving {db_id} -> {r.status_code}: {r.text[:300]}")


# Notion pins the title property to the leftmost column, so the title is
# always the thing the row *is*: a course, a category, an item.


def create_courses(headers, _deps):
    """Top level. One row per course per semester. Figures are job-written."""
    return _post("/databases", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": COURSES_TITLE}}],
        "description": [{"type": "text", "text": {"content":
            "One row per course. Set Course and Semester; everything else is "
            "written by the sync job. Open a row to manage its categories."}}],
        "properties": {
            "Course":   {"title": {}},
            "Semester": {"rich_text": {}},
            "Marks":    {"rich_text": {}},   # earned / graded weight
            "Percent":  {"number": {"format": "percent"}},
            "Updated":  {"date": {}},
            "Notes":    {"rich_text": {}},
        },
    }, headers)


def create_categories(headers, deps):
    """Middle level. Weight and Counts come from the syllabus."""
    return _post("/databases", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": CATEGORIES_TITLE}}],
        "description": [{"type": "text", "text": {"content":
            "One row per category of one course. Counts = how many contribute; "
            "leave blank when all of them do. Marks, Score and Dropped are "
            "written by the sync job."}}],
        "properties": {
            "Category": {"title": {}},
            "Course":   {"relation": {"database_id": deps[COURSES_TITLE],
                                      "single_property": {}}},
            "Weight":   {"number": {"format": "number"}},
            "Counts":   {"number": {"format": "number"}},
            "Marks":    {"rich_text": {}},   # raw rollup, e.g. 52/70
            "Score":    {"rich_text": {}},   # weighted, e.g. 10.80 / 15.00
            "Dropped":  {"rich_text": {}},
        },
    }, headers)


def create_marks(headers, deps):
    """Bottom level. One row per graded item."""
    return _post("/databases", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": MARKS_TITLE}}],
        "description": [{"type": "text", "text": {"content":
            "One row per graded item. Leave Score empty until it is marked - "
            "empty is not zero and is excluded from the standing."}}],
        "properties": {
            "Item":     {"title": {}},
            "Category": {"relation": {"database_id": deps[CATEGORIES_TITLE],
                                      "single_property": {}}},
            "Score":    {"number": {"format": "number"}},
            "Max":      {"number": {"format": "number"}},
            "Counted":  {"checkbox": {}},
            "Weight":   {"number": {"format": "number"}},
        },
    }, headers)


BUILDERS = {
    COURSES_TITLE: create_courses,
    CATEGORIES_TITLE: create_categories,
    MARKS_TITLE: create_marks,
}

ENV_NAMES = {
    COURSES_TITLE: "NOTION_COURSES_DB_ID",
    CATEGORIES_TITLE: "NOTION_CATEGORIES_DB_ID",
    MARKS_TITLE: "NOTION_MARKS_DB_ID",
}


def main() -> int:
    headers = _headers()
    existing = find_existing(headers)

    if "--print-ids" in sys.argv:
        for title, db_id in sorted(existing.items()):
            print(f"{title:14} {db_id}")
        return 0

    if "--recreate" in sys.argv:
        for title, db_id in existing.items():
            archive_database(db_id, headers)
            print(f"{title:14} archived {db_id}")
        existing = {}
        print()

    ids = {}
    for title in ORDER:
        if title in existing:
            ids[title] = existing[title]
            print(f"{title:14} exists   {ids[title]}")
        else:
            ids[title] = BUILDERS[title](headers, ids)["id"]
            print(f"{title:14} created  {ids[title]}")

    print()
    print("Add these to backend/.env and to the GitHub environment:")
    for title in ORDER:
        print(f"  {ENV_NAMES[title]}={ids[title]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
