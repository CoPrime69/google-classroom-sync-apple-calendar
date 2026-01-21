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
    
    # Ensure due_date is timezone-aware (IST)
    if due_date.tzinfo is None:
        due_date = Config.TIMEZONE.localize(due_date)
    
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
    # Ensure dt is timezone-aware (IST)
    if dt.tzinfo is None:
        dt = Config.TIMEZONE.localize(dt)
    
    # If before 7 AM, move to 7 AM same day
    if dt.hour < Config.NOTIFICATION_START_HOUR:
        # Replace time while preserving timezone info
        return dt.replace(
            hour=Config.NOTIFICATION_START_HOUR,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=dt.tzinfo
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


IST = Config.TIMEZONE  # Asia/Kolkata

def parse_iso_datetime(iso_string: str) -> datetime:
    """
    Parse Google Classroom ISO datetime safely.

    Handles:
    1. Explicit UTC timestamps (Z / +00:00)
    2. Local IST timestamps without timezone
    3. Google's 12:59 UTC = end-of-day quirk
    """

    # Parse ISO string
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))

    # CASE 1: Timezone-aware → convert to IST
    if dt.tzinfo is not None:
        dt_ist = dt.astimezone(IST)
    else:
        # CASE 2: Naive datetime → Google already means IST
        dt_ist = IST.localize(dt)

    # Google Classroom "end of day" bug:
    # 12:59 UTC → 18:29 IST → should mean 23:59 IST
    if dt_ist.hour == 18 and dt_ist.minute == 29:
        dt_ist = dt_ist.replace(
            hour=23,
            minute=59,
            second=0,
            microsecond=0
        )

    return dt_ist