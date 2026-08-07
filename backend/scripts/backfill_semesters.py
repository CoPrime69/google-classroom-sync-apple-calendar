#!/usr/bin/env python3
"""
Seed courses.semester from each Classroom course's creationTime.

Semester is normally typed into the dashboard. This script exists only to
label the courses that already accumulated in the database before the column
was added, so they do not all have to be filled in by hand.

Course state is deliberately not used: whether an old course is ARCHIVED is
the teacher's decision, not the student's, so some courses from a finished
semester stay ACTIVE indefinitely. creationTime clusters tightly around the
start of term and is reliable.

Prints a proposed label for every course and writes nothing unless --apply
is passed.

    python scripts/backfill_semesters.py            # preview
    python scripts/backfill_semesters.py --apply    # write
"""

import os
import sys

# scripts/README.md documents running these from the backend root. Python puts
# the script's own directory on sys.path rather than the caller's, so src/ is
# not importable without this.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.classroom.client import ClassroomClient
from src.database import Database

# Anchor: the semester in progress during Spring 2026 was the 6th.
ANCHOR_ORDINAL = 2026 * 2      # Spring 2026
ANCHOR_NUMBER = 6


def term_of(created_iso: str):
    """Map an ISO creation timestamp to (ordinal, human label)."""
    year = int(created_iso[0:4])
    month = int(created_iso[5:7])

    if 7 <= month <= 10:
        season, term_year = 'Autumn', year
    elif month >= 11:
        # Courses for a January term are created in Nov/Dec of the year before.
        season, term_year = 'Spring', year + 1
    else:
        season, term_year = 'Spring', year

    ordinal = term_year * 2 + (0 if season == 'Spring' else 1)
    number = ordinal - ANCHOR_ORDINAL + ANCHOR_NUMBER
    return ordinal, number, f'{season} {term_year}'


def ordinal_suffix(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')


def main() -> int:
    apply = '--apply' in sys.argv

    svc = ClassroomClient().service
    classroom = svc.courses().list(courseStates=['ACTIVE', 'ARCHIVED']).execute()
    created_by_id = {
        c['id']: c.get('creationTime')
        for c in classroom.get('courses', [])
    }

    db = Database()
    courses = db.client.table('courses').select('*').execute().data

    print(f'{len(courses)} courses in database, '
          f'{len(created_by_id)} known to Classroom')
    print()
    print(f'{"semester":10} {"current":10} {"created":11} name')
    print('-' * 82)

    updates = []
    for course in sorted(courses, key=lambda c: str(created_by_id.get(c['id']))):
        created = created_by_id.get(course['id'])
        existing = course.get('semester') or '-'

        if not created:
            print(f'{"?":10} {existing:10} {"unknown":11} {course["name"][:40]}')
            continue

        _, number, _ = term_of(created)
        label = f'{number}{ordinal_suffix(number)} sem'
        print(f'{label:10} {existing:10} {created[:10]:11} {course["name"][:40]}')

        if course.get('semester') != label:
            updates.append((course['id'], label))

    print()
    if not updates:
        print('Nothing to change.')
        return 0

    if not apply:
        print(f'{len(updates)} course(s) would be updated. '
              f'Re-run with --apply to write.')
        return 0

    for course_id, label in updates:
        db.client.table('courses').update({'semester': label}).eq('id', course_id).execute()
    print(f'Updated {len(updates)} course(s).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
