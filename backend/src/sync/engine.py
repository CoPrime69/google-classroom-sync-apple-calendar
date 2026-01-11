"""
Core sync engine.
Orchestrates the synchronization between Google Classroom and Apple Reminders.
"""

from typing import Dict, List, Any
from datetime import datetime
from ..database import Database
from ..classroom import ClassroomClient
from ..reminders import RemindersClient
from ..utils import (
    calculate_alarms,
    is_deadline_extended,
    is_past_deadline,
    format_category_title,
    get_ist_now,
    parse_iso_datetime
)


class SyncEngine:
    """Core synchronization engine"""
    
    def __init__(self):
        self.db = Database()
        self.classroom = ClassroomClient()
        self.reminders = RemindersClient()
        
        # Stats for logging
        self.stats = {
            'assignments_processed': 0,
            'reminders_created': 0,
            'reminders_updated': 0,
            'reminders_cancelled': 0
        }
    
    def sync(self):
        """
        Main sync orchestration.
        Performs complete sync cycle.
        """
        print("=" * 60)
        print(f"Starting sync at {get_ist_now().strftime('%Y-%m-%d %I:%M %p IST')}")
        print("=" * 60)
        
        # Step 1: Sync courses and categories
        self._sync_courses_and_categories()
        
        # Step 2: Get enabled courses
        enabled_courses = self.db.get_enabled_courses()
        print(f"\nEnabled courses: {len(enabled_courses)}")
        
        if not enabled_courses:
            print("⚠️  No enabled courses. Enable courses in the frontend dashboard.")
            return self.stats
        
        # Step 3: Process each course
        for course in enabled_courses:
            self._process_course(course)
        
        # Step 4: Print summary
        self._print_summary()
        
        return self.stats
    
    def _sync_courses_and_categories(self):
        """Sync courses and categories from Classroom to database"""
        print("\n📚 Syncing courses and categories...")
        
        courses = self.classroom.get_courses()
        
        for course in courses:
            # Upsert course
            self.db.upsert_course(course)
            
            # Sync topics/categories
            topics = self.classroom.get_course_topics(course['id'])
            for topic in topics:
                self.db.upsert_category(topic)
        
        print(f"   Synced {len(courses)} courses")
    
    def _process_course(self, course: Dict[str, Any]):
        """Process all assignments for a course"""
        course_id = course['id']
        course_name = course['name']
        
        print(f"\n📖 Processing: {course_name}")
        
        # Get enabled categories for this course
        enabled_categories = self.db.get_enabled_categories(course_id)
        enabled_category_ids = {cat['id'] for cat in enabled_categories}
        
        # Check if course has sync_without_categories enabled
        sync_without_categories = course.get('sync_without_categories', False)
        
        if not enabled_category_ids and not sync_without_categories:
            print("   ⚠️  No enabled categories (enable 'sync_without_categories' to sync all)")
            return
        
        # Fetch coursework from Classroom
        coursework_list = self.classroom.get_coursework(course_id)
        
        for coursework in coursework_list:
            # Skip if no due date
            if not coursework.get('due_date'):
                continue
            
            # Skip if category not enabled (unless sync_without_categories is on)
            if not sync_without_categories:
                if coursework.get('category_id') and coursework['category_id'] not in enabled_category_ids:
                    continue
            
            self._process_assignment(coursework, course)
    
    def _process_assignment(self, coursework: Dict[str, Any], course: Dict[str, Any]):
        """Process a single assignment"""
        assignment_id = coursework['id']
        course_id = coursework['course_id']
        
        self.stats['assignments_processed'] += 1
        
        # Check if assignment exists in DB
        existing = self.db.get_assignment(assignment_id)
        
        if existing:
            # Assignment exists - check if it needs updating
            self._handle_existing_assignment(existing, coursework, course)
        else:
            # New assignment
            self._handle_new_assignment(coursework, course)
    
    def _handle_new_assignment(self, coursework: Dict[str, Any], course: Dict[str, Any]):
        """Handle new assignment"""
        assignment_id = coursework['id']
        due_date = parse_iso_datetime(coursework['due_date'])
        
        # Check if already past deadline
        if is_past_deadline(due_date):
            print(f"   ⏭️  Skipping past assignment: {coursework['title']}")
            return
        
        print(f"   ➕ New: {coursework['title']}")
        
        # Get category name for denormalization
        category_name = None
        if coursework.get('category_id'):
            category = self.db.get_category(coursework['category_id'])
            if category:
                category_name = category['name']
        
        # Create in database with all required fields
        assignment_data = {
            **coursework,
            'category_name': category_name,
            'last_seen_due_date': coursework['due_date'],  # Initial value
            'submission_checked_post_deadline': False
        }
        self.db.upsert_assignment(assignment_data)
        
        # Create reminder
        self._create_reminder(coursework, course, due_date, category_name)
        
        self.stats['reminders_created'] += 1
    
    def _handle_existing_assignment(
        self,
        existing: Dict[str, Any],
        coursework: Dict[str, Any],
        course: Dict[str, Any]
    ):
        """Handle existing assignment - check for updates"""
        assignment_id = existing['id']
        
        # Skip if marked dead (CRITICAL: prevents stale extension logic)
        if existing.get('is_dead'):
            return
        
        new_due_date = parse_iso_datetime(coursework['due_date'])
        old_due_date = parse_iso_datetime(existing['due_date']) if existing.get('due_date') else None
        last_seen_due_date = parse_iso_datetime(existing['last_seen_due_date']) if existing.get('last_seen_due_date') else old_due_date
        
        # Check submission status (cache to avoid double API calls)
        submission_status = self.classroom.get_submission_status(
            coursework['course_id'],
            assignment_id
        )
        
        # If submitted, mark dead and cancel alarms
        if submission_status == 'SUBMITTED':
            print(f"   ✅ Submitted: {coursework['title']}")
            self.db.mark_assignment_dead(assignment_id)
            self.db.update_submission_status(assignment_id, 'SUBMITTED')
            self._cancel_reminder(existing, course)
            self.stats['reminders_cancelled'] += 1
            return
        
        # Check if past deadline
        if is_past_deadline(new_due_date):
            # Only do final submission check if not already done
            if not existing.get('submission_checked_post_deadline'):
                # Use cached submission_status (already fetched above)
                final_status = submission_status
                
                self.db.mark_submission_checked_post_deadline(assignment_id)
                
                if final_status != 'SUBMITTED':
                    print(f"   ⏰ Past deadline (not submitted): {coursework['title']}")
                else:
                    print(f"   ✅ Submitted (post-deadline check): {coursework['title']}")
            
            self.db.mark_assignment_dead(assignment_id)
            self._cancel_reminder(existing, course)
            self.stats['reminders_cancelled'] += 1
            return
        
        # Check for deadline extension (compare against last_seen_due_date)
        if last_seen_due_date and is_deadline_extended(last_seen_due_date, new_due_date):
            print(f"   🔄 Deadline extended: {coursework['title']}")
            self.db.update_due_date(assignment_id, coursework['due_date'])
            
            # Get category name
            category_name = existing.get('category_name')
            if coursework.get('category_id') and coursework['category_id'] != existing.get('category_id'):
                category = self.db.get_category(coursework['category_id'])
                if category:
                    category_name = category['name']
            
            self._update_reminder(existing, coursework, course, new_due_date, category_name)
            self.stats['reminders_updated'] += 1
            return
        
        # Check for category change
        if existing.get('category_id') != coursework.get('category_id'):
            print(f"   🏷️  Category changed: {coursework['title']}")
            
            # Get new category name
            category_name = None
            if coursework.get('category_id'):
                category = self.db.get_category(coursework['category_id'])
                if category:
                    category_name = category['name']
            
            # Update with new category name
            self.db.upsert_assignment({
                **coursework,
                'category_name': category_name
            })
            self._update_reminder(existing, coursework, course, new_due_date, category_name)
            self.stats['reminders_updated'] += 1
            return
    
    def _create_reminder(self, coursework: Dict[str, Any], course: Dict[str, Any], due_date: datetime, category_name: str = None):
        """Create new reminder in Apple Reminders"""
        assignment_id = coursework['id']
        
        # Get category name if not provided
        if not category_name:
            category_name = "GENERAL"
            if coursework.get('category_id'):
                category = self.db.get_category(coursework['category_id'])
                if category:
                    category_name = category['name']
        
        # Format title
        title = format_category_title(
            category_name,
            coursework['title'],
            course['name']
        )
        
        # Generate fingerprint for recovery
        notes_fingerprint = f"classroom_assignment_id={assignment_id};course_id={course['id']}"
        
        # Calculate alarms
        alarms = calculate_alarms(due_date)
        
        if not alarms:
            print(f"      ⚠️  No valid alarm times")
            return
        
        # Get course_code and calendar_name from DB
        # Priority: calendar_name > course_code > course name
        calendar_name = course.get('calendar_name') or course['name']
        course_code = course.get('course_code') or course['name']
        
        # Create reminder with new parameters
        reminder_uid = self.reminders.create_reminder(
            list_name=calendar_name,
            title=title,  # This is actually full title, will be reformatted in client
            notes=notes_fingerprint,
            due_date=due_date,
            alarms=alarms,
            color=course.get('color', '#007AFF'),
            course_code=course_code,
            category_label=category_name,
            full_assignment_title=coursework['title']
        )
        
        # Update DB with reminder UID and fingerprint
        self.db.upsert_assignment({
            'id': assignment_id,
            'reminder_uid': reminder_uid,
            'reminder_notes_fingerprint': notes_fingerprint,
            **coursework
        })
        
        print(f"      Created with {len(alarms)} alarms")
    
    def _update_reminder(
        self,
        existing: Dict[str, Any],
        coursework: Dict[str, Any],
        course: Dict[str, Any],
        due_date: datetime,
        category_name: str = None
    ):
        """Update existing reminder"""
        assignment_id = coursework['id']
        reminder_uid = existing.get('reminder_uid')
        
        # If UID is missing, try to recover using fingerprint
        if not reminder_uid:
            # Get calendar_name from DB or fall back to course name
            calendar_name = course.get('calendar_name') or course['name']
            fingerprint = existing.get('reminder_notes_fingerprint')
            if fingerprint:
                # Try to find by fingerprint
                reminder_uid = self.reminders.find_reminder_by_notes(
                    calendar_name,
                    fingerprint
                )
            
            # Fallback to assignment ID search
            if not reminder_uid:
                reminder_uid = self.reminders.find_reminder_by_notes(
                    calendar_name,
                    assignment_id
                )
        
        if not reminder_uid:
            print(f"      ⚠️  Reminder UID not found, creating new")
            self._create_reminder(coursework, course, due_date, category_name)
            return
        
        # Get category name if not provided
        if not category_name:
            category_name = existing.get('category_name', "GENERAL")
            if coursework.get('category_id'):
                category = self.db.get_category(coursework['category_id'])
                if category:
                    category_name = category['name']
        
        # Format title
        title = format_category_title(
            category_name,
            coursework['title'],
            course['name']
        )
        
        # Generate fingerprint
        notes_fingerprint = f"classroom_assignment_id={assignment_id};course_id={course['id']}"
        
        # Calculate new alarms
        alarms = calculate_alarms(due_date)
        
        if not alarms:
            print(f"      ⚠️  No valid alarm times")
            return
        
        # Get course_code and calendar_name from DB
        # Priority: calendar_name > course_code > course name
        calendar_name = course.get('calendar_name') or course['name']
        course_code = course.get('course_code') or course['name']
        
        # Update reminder with new parameters
        self.reminders.update_reminder(
            list_name=calendar_name,
            reminder_uid=reminder_uid,
            title=title,
            notes=notes_fingerprint,
            due_date=due_date,
            alarms=alarms,
            color=course.get('color', '#007AFF'),
            course_code=course_code,
            category_label=category_name,
            full_assignment_title=coursework['title']
        )
        
        print(f"      Updated with {len(alarms)} alarms")
    
    def _cancel_reminder(self, existing: Dict[str, Any], course: Dict[str, Any]):
        """Cancel/delete reminder"""
        reminder_uid = existing.get('reminder_uid')
        
        # Get calendar_name from DB or fall back to course name
        calendar_name = course.get('calendar_name') or course['name']
        
        if reminder_uid:
            self.reminders.delete_reminder(
                list_name=calendar_name,
                reminder_uid=reminder_uid
            )
        
        # Clean up database alarm rows to prevent stale state
        self.db.delete_alarms(existing['id'])
        
        print(f"      Cancelled reminder")
    
    def _print_summary(self):
        """Print sync summary"""
        print("\n" + "=" * 60)
        print("SYNC SUMMARY")
        print("=" * 60)
        print(f"Assignments processed: {self.stats['assignments_processed']}")
        print(f"Reminders created:     {self.stats['reminders_created']}")
        print(f"Reminders updated:     {self.stats['reminders_updated']}")
        print(f"Reminders cancelled:   {self.stats['reminders_cancelled']}")
        print("=" * 60)
