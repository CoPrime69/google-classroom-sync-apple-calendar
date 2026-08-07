"""
Entry point for the grade sync.

Separate from main.py on purpose: grades and calendar reminders fail for
different reasons, and a Notion outage should not stop assignment reminders
being created.
"""

import sys
import traceback

from src.config import Config
from src.grades.sync import GradeSync
from src.utils import get_ist_now


def main() -> int:
    try:
        Config.validate()
        Config.validate_notion()

        print("Starting grade sync")
        print(f"Timestamp: {get_ist_now().strftime('%Y-%m-%d %I:%M %p IST')}")

        stats = GradeSync().run()

        print()
        print("=" * 60)
        print("GRADE SYNC SUMMARY")
        print("=" * 60)
        for label in ("courses", "groups", "components", "snapshots"):
            print(f"{label.capitalize() + ':':14} {stats[label]}")
        print("=" * 60)
        print()
        print("Grade sync completed successfully")
        return 0

    except Exception as exc:
        print(f"\nGrade sync failed: {exc}")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
