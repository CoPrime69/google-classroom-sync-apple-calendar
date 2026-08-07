#!/usr/bin/env python3
"""
Seed Grade Setup with published evaluation policies.

The policies below are transcribed from each course's syllabus. Editing them
here is not the normal way to change the tracker -- once seeded, everything is
edited in Notion. This exists so the first semester does not have to be typed
in by hand.

    python scripts/seed_grade_setup.py            # preview
    python scripts/seed_grade_setup.py --apply    # write

Idempotent: a course already present in Grade Setup is skipped entirely rather
than duplicated.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import dotenv_values

from src.grades.notion import NotionClient

SEMESTER = "7th sem"

# (weight, counts) -- counts None means every component counts, used where the
# number of items is open-ended and none are dropped.
POLICIES = {
    "CSL7360": [                       # Computer Vision
        ("Assignments",        10.0, 2),
        ("Quizzes",            15.0, 5),   # "5-7 quizzes": best 5 either way
        ("Mini Project",       15.0, 1),
        ("Minor",              20.0, 1),
        ("Major",              40.0, 1),
    ],
    "MSL4010": [                       # Introduction to Business and Management
        ("Participation",      10.0, 1),
        ("Group Project",      15.0, 1),
        ("Minor",              25.0, 1),
        ("Major",              50.0, 1),
    ],
    "LAL7490": [                       # Indian Economic Development and Policy
        ("Assignments",        25.0, 2),
        ("Minor",              25.0, 1),
        ("Major",              50.0, 1),
    ],
    "CIL4010": [                       # Environmental Science
        ("Minor",              20.0, 1),
        ("Major",              50.0, 1),
        ("Class Assignments",  10.0, None),   # "assigned as needed"
        ("PPT presentation",   10.0, 1),
        ("Video presentation", 10.0, 1),
    ],
}


def main() -> int:
    apply = "--apply" in sys.argv

    env = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env"))

    client = NotionClient(
        token=env["NOTION_API_KEY"].strip(),
        courses_db=env["NOTION_COURSES_DB_ID"].strip(),
        categories_db=env["NOTION_CATEGORIES_DB_ID"].strip(),
        marks_db=env["NOTION_MARKS_DB_ID"].strip(),
    )

    existing = client.fetch_courses()
    have = {
        (r["course"] or "").strip().upper()
        for r in existing if not r["archived"]
    }

    print(f"Courses currently holds {len(existing)} row(s)")
    print()

    planned = []
    for course, groups in POLICIES.items():
        if course.upper() in have:
            print(f"{course}: already present, skipping")
            continue
        total = sum(w for _, w, _ in groups)
        flag = "" if abs(total - 100.0) < 0.01 else f"  <-- sums to {total}, not 100"
        print(f"{course}: {len(groups)} groups, {total:g}%{flag}")
        for name, weight, counts in groups:
            shown = "all" if counts is None else str(counts)
            print(f"    {name:20} {weight:5g}%  counts={shown}")
            planned.append((course, name, weight, counts))
        print()

    if not planned:
        print("Nothing to add.")
        return 0

    if not apply:
        print(f"{len(planned)} row(s) would be created. Re-run with --apply.")
        return 0

    # Course rows first: each category needs its parent to relate to.
    course_pages = {}
    for course in dict.fromkeys(c for c, _, _, _ in planned):
        course_pages[course] = client.create_course_row(course, SEMESTER)
        print(f"  created course {course}")

    for course, name, weight, counts in planned:
        client.create_category_row(course_pages[course], name, weight, counts)
        print(f"    created {course} / {name}")

    print()
    print(f"Created {len(planned)} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
