#!/usr/bin/env python3
"""
Create the Courses database and seed each course's own tables.

Layout: one top-level Courses database. Each course row's page holds two
child databases of its own, so opening a course shows only that course's
components and marks.

    Courses (database)
      CSL7360  ·  7th sem     (standing lives on the Progress table)
        Components   Quizzes  15%  counts 5  ·  52/70  ·  dropped Quiz 5
        Marks        Quiz 1   8/10  ·  counted  ·  w 3.00

    python scripts/bootstrap_notion.py             # preview
    python scripts/bootstrap_notion.py --apply     # create
    python scripts/bootstrap_notion.py --recreate  # archive all, rebuild

Idempotent: a course already present keeps its tables and rows.

POLICIES below are the published evaluation schemes, transcribed once so the
first semester need not be typed by hand. After seeding, everything is edited
in Notion; a later semester means adding rows there, not editing this file.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from dotenv import dotenv_values

from src.grades.notion import NotionClient

PARENT_PAGE_ID = "3b57b66497ed803ea58ef30a3c478779"
COURSES_TITLE = "Courses"
PROGRESS_TITLE = "Progress"
SEMESTER = "7th sem"

# (component, weight, counts) -- counts None means every component counts,
# used where the number of items is open-ended and none are dropped.
POLICIES = {
    "CSL7360": [                          # Computer Vision
        ("Assignments",        10.0, 2),
        ("Quizzes",            15.0, 5),  # "5-7 quizzes": best 5 either way
        ("Mini Project",       15.0, 1),
        ("Minor",              20.0, 1),
        ("Major",              40.0, 1),
    ],
    "MSL4010": [                          # Introduction to Business and Management
        ("Participation",      10.0, 1),
        ("Group Project",      15.0, 1),
        ("Minor",              25.0, 1),
        ("Major",              50.0, 1),
    ],
    "LAL7490": [                          # Indian Economic Development and Policy
        ("Assignments",        25.0, 2),
        ("Minor",              25.0, 1),
        ("Major",              50.0, 1),
    ],
    "CIL4010": [                          # Environmental Science
        ("Minor",              20.0, 1),
        ("Major",              50.0, 1),
        ("Class Assignments",  10.0, None),   # "assigned as needed"
        ("PPT presentation",   10.0, 1),
        ("Video presentation", 10.0, 1),
    ],
}

# Courses is input only. Everything computed lives on Progress, so this table
# stays a clean list of what you are taking.
COURSES_PROPERTIES = {
    "Course":   {"title": {}},
    "Semester": {"rich_text": {}},
}

# Progress is written entirely by the job.
PROGRESS_PROPERTIES = {
    "Course":   {"title": {}},
    "Semester": {"rich_text": {}},
    "Marks":    {"rich_text": {}},   # earned / graded weight
    "Percent":  {"number": {"format": "percent"}},
    "Updated":  {"date": {}},
    "Notes":    {"rich_text": {}},
}


def _env():
    return dotenv_values(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env"))


def _headers(token):
    return {"Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"}


def find_db(headers, title):
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(
            f"https://api.notion.com/v1/blocks/{PARENT_PAGE_ID}/children",
            params=params, headers=headers, timeout=30)
        r.raise_for_status()
        body = r.json()
        for block in body.get("results", []):
            if (block.get("type") == "child_database"
                    and block["child_database"]["title"] == title):
                return block["id"]
        if not body.get("has_more"):
            return None
        cursor = body.get("next_cursor")


def archive_all(headers):
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(
            f"https://api.notion.com/v1/blocks/{PARENT_PAGE_ID}/children",
            params=params, headers=headers, timeout=30)
        r.raise_for_status()
        body = r.json()
        for block in body.get("results", []):
            if block.get("type") == "child_database":
                requests.patch(
                    f"https://api.notion.com/v1/databases/{block['id']}",
                    json={"archived": True}, headers=headers, timeout=30)
                print(f"  archived {block['child_database']['title']}")
                time.sleep(0.34)
        if not body.get("has_more"):
            return
        cursor = body.get("next_cursor")


def create_db(headers, title, properties, description):
    r = requests.post("https://api.notion.com/v1/databases", headers=headers,
                      timeout=30, json={
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": title}}],
        "description": [{"type": "text", "text": {"content": description}}],
        "properties": properties,
    })
    if not r.ok:
        raise SystemExit(f"creating {title} -> {r.status_code}: {r.text[:300]}")
    return r.json()["id"]


def main() -> int:
    env = _env()
    token = env["NOTION_API_KEY"].strip()
    headers = _headers(token)
    apply = "--apply" in sys.argv or "--recreate" in sys.argv

    if "--recreate" in sys.argv:
        archive_all(headers)
        print()

    courses_db = find_db(headers, COURSES_TITLE)
    progress_db = find_db(headers, PROGRESS_TITLE)

    if not apply and not (courses_db and progress_db):
        print(f"{COURSES_TITLE} and {PROGRESS_TITLE} would be created")
        print("Re-run with --apply.")
        return 0

    if not courses_db:
        courses_db = create_db(
            headers, COURSES_TITLE, COURSES_PROPERTIES,
            "One row per course you are taking. Open a row to define its "
            "components and enter marks. Overall standing is on Progress.")
        print(f"{COURSES_TITLE:10} created  {courses_db}")
    else:
        print(f"{COURSES_TITLE:10} exists   {courses_db}")

    if not progress_db:
        progress_db = create_db(
            headers, PROGRESS_TITLE, PROGRESS_PROPERTIES,
            "Overall standing per course, written by the sync job. Editing "
            "anything here is pointless - it is overwritten next run.")
        print(f"{PROGRESS_TITLE:10} created  {progress_db}")
    else:
        print(f"{PROGRESS_TITLE:10} exists   {progress_db}")

    client = NotionClient(token=token, courses_db=courses_db)
    have = {(c["course"] or "").strip().upper()
            for c in client.fetch_courses() if not c["archived"]}

    print()
    todo = {c: g for c, g in POLICIES.items() if c.upper() not in have}
    for course in POLICIES:
        if course.upper() in have:
            print(f"{course}: already present, skipping")

    if not todo:
        print("\nNothing to add.")
        print(f"\nNOTION_COURSES_DB_ID={courses_db}")
        return 0

    for course, groups in todo.items():
        total = sum(w for _, w, _ in groups)
        flag = "" if abs(total - 100.0) < 0.01 else f"  <-- {total}%, not 100"
        print(f"{course}: {len(groups)} components, {total:g}%{flag}")

    if not apply:
        print(f"\n{len(todo)} course(s) would be created. Re-run with --apply.")
        return 0

    print()
    for course, groups in todo.items():
        made = client.create_course(course, SEMESTER)
        print(f"  {course}: course row + Components + Marks tables")
        for name, weight, counts in groups:
            client.create_component(made["Components"], name, weight, counts)
            shown = "all" if counts is None else counts
            print(f"      {name:20} {weight:5g}%  counts={shown}")

    print()
    print(f"NOTION_COURSES_DB_ID={courses_db}")
    print(f"NOTION_PROGRESS_DB_ID={progress_db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
