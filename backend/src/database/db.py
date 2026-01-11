"""
Supabase database interface.
Handles all database operations for the sync system.
"""

from supabase import create_client, Client
from typing import List, Dict, Optional, Any
from datetime import datetime
import pytz
from ..config import Config


class Database:
    """Database interface for Supabase"""
    
    def __init__(self):
        self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    
    # ========================================
    # COURSES
    # ========================================
    
    def get_enabled_courses(self) -> List[Dict[str, Any]]:
        """Get all enabled courses"""
        response = self.client.table('courses').select('*').eq('enabled', True).execute()
        return response.data
    
    def upsert_course(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a course"""
        response = self.client.table('courses').upsert(course_data).execute()
        return response.data[0] if response.data else None
    
    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific course"""
        response = self.client.table('courses').select('*').eq('id', course_id).execute()
        return response.data[0] if response.data else None
    
    # ========================================
    # CATEGORIES
    # ========================================
    
    def get_enabled_categories(self, course_id: str) -> List[Dict[str, Any]]:
        """Get all enabled categories for a course"""
        response = (self.client.table('categories')
                   .select('*')
                   .eq('course_id', course_id)
                   .eq('enabled', True)
                   .execute())
        return response.data
    
    def upsert_category(self, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a category"""
        response = self.client.table('categories').upsert(category_data).execute()
        return response.data[0] if response.data else None
    
    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific category"""
        response = self.client.table('categories').select('*').eq('id', category_id).execute()
        return response.data[0] if response.data else None
    
    # ========================================
    # ASSIGNMENTS
    # ========================================
    
    def get_assignment(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific assignment"""
        response = self.client.table('assignments').select('*').eq('id', assignment_id).execute()
        return response.data[0] if response.data else None
    
    def get_active_assignments(self) -> List[Dict[str, Any]]:
        """Get all active (non-dead) assignments"""
        response = (self.client.table('assignments')
                   .select('*')
                   .eq('is_dead', False)
                   .execute())
        return response.data
    
    def upsert_assignment(self, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update an assignment
        
        CRITICAL: Protects is_dead and submission_checked_post_deadline flags
        from being unintentionally overwritten during partial updates.
        """
        assignment_data['updated_at'] = datetime.now(Config.TIMEZONE).isoformat()
        
        # Protect critical flags from accidental overwrites
        PROTECTED_FIELDS = {'is_dead', 'submission_checked_post_deadline'}
        existing = self.get_assignment(assignment_data['id']) if 'id' in assignment_data else None
        
        if existing:
            for field in PROTECTED_FIELDS:
                if field in existing and field not in assignment_data:
                    assignment_data[field] = existing[field]
        
        # Set last_seen_due_date on first insert
        if 'due_date' in assignment_data and 'last_seen_due_date' not in assignment_data:
            assignment_data['last_seen_due_date'] = assignment_data['due_date']
        
        # Generate reminder notes fingerprint
        if 'id' in assignment_data and 'course_id' in assignment_data:
            assignment_data['reminder_notes_fingerprint'] = (
                f"classroom_assignment_id={assignment_data['id']};"
                f"course_id={assignment_data['course_id']}"
            )
        
        response = self.client.table('assignments').upsert(assignment_data).execute()
        return response.data[0] if response.data else None
    
    def mark_assignment_dead(self, assignment_id: str):
        """Mark an assignment as dead (no further processing)"""
        response = (self.client.table('assignments')
                   .update({
                       'is_dead': True,
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', assignment_id)
                   .execute())
        return response.data[0] if response.data else None
    
    def update_submission_status(self, assignment_id: str, status: str):
        """Update assignment submission status"""
        response = (self.client.table('assignments')
                   .update({
                       'submission_status': status,
                       'last_checked': datetime.now(Config.TIMEZONE).isoformat(),
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', assignment_id)
                   .execute())
        return response.data[0] if response.data else None
    
    def mark_submission_checked_post_deadline(self, assignment_id: str):
        """Mark that assignment has been checked after deadline"""
        response = (self.client.table('assignments')
                   .update({
                       'submission_checked_post_deadline': True,
                       'last_checked': datetime.now(Config.TIMEZONE).isoformat(),
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', assignment_id)
                   .execute())
        return response.data[0] if response.data else None
    
    def update_due_date(self, assignment_id: str, new_due_date: str):
        """Update assignment due date and track last seen value
        
        CRITICAL: Updates both due_date AND last_seen_due_date to prevent
        infinite extension detection loops on subsequent runs.
        """
        response = (self.client.table('assignments')
                   .update({
                       'due_date': new_due_date,
                       'last_seen_due_date': new_due_date,  # CRITICAL: Must update both
                       'submission_checked_post_deadline': False,  # Reset flag
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', assignment_id)
                   .execute())
        return response.data[0] if response.data else None
    
    # ========================================
    # ALARMS
    # ========================================
    
    def get_alarms(self, assignment_id: str) -> List[Dict[str, Any]]:
        """Get all alarms for an assignment"""
        response = (self.client.table('alarms')
                   .select('*')
                   .eq('assignment_id', assignment_id)
                   .execute())
        return response.data
    
    def upsert_alarm(self, alarm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update an alarm"""
        response = self.client.table('alarms').upsert(alarm_data).execute()
        return response.data[0] if response.data else None
    
    def mark_alarm_fired(self, assignment_id: str, alarm_type: str):
        """Mark an alarm as fired"""
        response = (self.client.table('alarms')
                   .update({
                       'fired': True,
                       'fired_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('assignment_id', assignment_id)
                   .eq('alarm_type', alarm_type)
                   .execute())
        return response.data
    
    def delete_alarms(self, assignment_id: str):
        """Delete all alarms for an assignment"""
        response = (self.client.table('alarms')
                   .delete()
                   .eq('assignment_id', assignment_id)
                   .execute())
        return response.data
    
    # ========================================
    # CRON FAILURES (singleton)
    # ========================================
    
    def get_failure_state(self) -> Optional[Dict[str, Any]]:
        """Get current failure state (singleton row)"""
        response = self.client.table('cron_failures').select('*').eq('id', 1).execute()
        return response.data[0] if response.data else None
    
    def record_success(self):
        """Record successful cron execution"""
        response = (self.client.table('cron_failures')
                   .update({
                       'last_success': datetime.now(Config.TIMEZONE).isoformat(),
                       'consecutive_failures': 0,
                       'alert_sent': False,
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', 1)
                   .execute())
        return response.data
    
    def record_failure(self) -> int:
        """Record failed cron execution and return consecutive failure count"""
        failure_state = self.get_failure_state()
        consecutive = (failure_state.get('consecutive_failures', 0) + 1) if failure_state else 1
        
        response = (self.client.table('cron_failures')
                   .update({
                       'consecutive_failures': consecutive,
                       'last_failure': datetime.now(Config.TIMEZONE).isoformat(),
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', 1)
                   .execute())
        
        return consecutive
    
    def mark_alert_sent(self):
        """Mark that failure alert has been sent"""
        response = (self.client.table('cron_failures')
                   .update({
                       'alert_sent': True,
                       'updated_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .eq('id', 1)
                   .execute())
        return response.data
    
    # ========================================
    # CRON LOGS
    # ========================================
    
    def create_cron_log(self) -> int:
        """Create a new cron log entry"""
        response = (self.client.table('cron_logs')
                   .insert({
                       'status': 'RUNNING',
                       'started_at': datetime.now(Config.TIMEZONE).isoformat()
                   })
                   .execute())
        return response.data[0]['id']
    
    def update_cron_log(self, log_id: int, updates: Dict[str, Any]):
        """Update cron log with results"""
        updates['completed_at'] = datetime.now(Config.TIMEZONE).isoformat()
        response = (self.client.table('cron_logs')
                   .update(updates)
                   .eq('id', log_id)
                   .execute())
        return response.data
