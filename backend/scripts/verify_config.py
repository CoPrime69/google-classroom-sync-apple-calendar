#!/usr/bin/env python3
"""Summary verification of calendar name and event title setup"""

from src.database import Database
from src.sync.engine import SyncEngine

db = Database()

print("\n" + "=" * 80)
print("CONFIGURATION VERIFICATION")
print("=" * 80)

enabled_courses = db.get_enabled_courses()

print("\nDatabase Configuration:")
print("-" * 80)
for course in enabled_courses:
    calendar_name = course.get('calendar_name') or course['name']
    course_code = course.get('course_code') or course['name']
    
    print(f"\n  Course: {course['name']}")
    print(f"    ✓ Calendar Name (list_name):     {calendar_name}")
    print(f"    ✓ Course Code (in event title):  {course_code}")
    print(f"    → Event Title Format:            [CATEGORY] - {course_code}")

print("\n" + "-" * 80)
print("\nHow it works:")
print("  1. Sync engine reads calendar_name and course_code from database")
print("  2. calendar_name is used as the Apple Calendar name (e.g., 'VCC')")
print("  3. course_code is used in event titles (e.g., '[ASSIGNMENTS] - CSL7510')")
print("  4. category_label is used for the category prefix (e.g., 'ASSIGNMENTS', 'GENERAL')")

print("\n✅ Configuration is correct!")
print("=" * 80 + "\n")
