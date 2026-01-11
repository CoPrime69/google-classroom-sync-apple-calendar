"""
Utility functions for date/time calculations and alarm scheduling.
"""

from datetime import datetime, timedelta
from typing import List
from ..config import Config


def calculate_alarms(due_date: datetime, current_time: datetime = None) -> List[datetime]:
    """
    Calculate alarm times based on due date and notification window.
    
    Args:
        due_date: Assignment due date
        current_time: Current time (defaults to now)
        
    Returns:
        List of alarm datetimes
    """
    if current_time is None:
        current_time = datetime.now(Config.TIMEZONE)
    
    alarms = []
    
    for interval_hours in Config.ALARM_INTERVALS:
        alarm_time = due_date - timedelta(hours=interval_hours)
        
        # Skip if alarm is in the past
        if alarm_time <= current_time:
            continue
        
        # Apply time window constraints
        alarm_time = apply_time_window(alarm_time)
        
        alarms.append(alarm_time)
    
    return alarms


def apply_time_window(dt: datetime) -> datetime:
    """
    Apply notification time window constraints.
    No notifications before 7 AM or after midnight.
    
    Args:
        dt: Original datetime
        
    Returns:
        Adjusted datetime
    """
    # If before 7 AM, move to 7 AM same day
    if dt.hour < Config.NOTIFICATION_START_HOUR:
        return dt.replace(
            hour=Config.NOTIFICATION_START_HOUR,
            minute=0,
            second=0,
            microsecond=0
        )
    
    # If after midnight (next day), keep as is
    # The constraint is no NEW alarms after midnight, but if due date is past midnight,
    # we still need to support it
    
    return dt


def is_deadline_extended(old_due: datetime, new_due: datetime) -> bool:
    """
    Check if deadline has been extended.
    
    Args:
        old_due: Old due date
        new_due: New due date
        
    Returns:
        True if deadline was extended
    """
    return new_due > old_due


def is_past_deadline(due_date: datetime, current_time: datetime = None) -> bool:
    """
    Check if assignment deadline has passed.
    
    Args:
        due_date: Assignment due date
        current_time: Current time (defaults to now)
        
    Returns:
        True if past deadline
    """
    if current_time is None:
        current_time = datetime.now(Config.TIMEZONE)
    
    return current_time > due_date


def format_category_title(category_name: str, assignment_title: str, course_name: str = None) -> str:
    """
    Format reminder title with category prefix.
    
    Args:
        category_name: Category/topic name
        assignment_title: Assignment title
        course_name: Optional course name to append
        
    Returns:
        Formatted title
    """
    title = f"[{category_name.upper()}] {assignment_title}"
    
    if course_name:
        title += f" – {course_name}"
    
    return title


def get_ist_now() -> datetime:
    """Get current time in IST timezone"""
    return datetime.now(Config.TIMEZONE)


def parse_iso_datetime(iso_string: str) -> datetime:
    """
    Parse ISO datetime string to timezone-aware datetime.
    Fixes Google Classroom's quirk: they store "due by end of day" as 12:59 UTC
    which becomes 18:29 IST. We convert this to 23:59 IST (actual end of day).
    
    Args:
        iso_string: ISO format datetime string
        
    Returns:
        Timezone-aware datetime (adjusted to 23:59 IST if it's Google's default 18:29)
    """
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    dt_ist = dt.astimezone(Config.TIMEZONE)
    
    # CRITICAL FIX: Google Classroom stores "due by end of day" as 12:59 UTC
    # which becomes 18:29 IST (6:29 PM). Convert to actual end of day (23:59 IST)
    if dt_ist.hour == 18 and dt_ist.minute == 29:
        # Replace with 11:59 PM IST (end of day)
        dt_ist = dt_ist.replace(hour=23, minute=59, second=0)
    
    return dt_ist
