"""
Apple Calendar integration via CalDAV.
Handles creation, update, and deletion of calendar events with alarms.
Note: Switched from VTODO (Reminders) to VEVENT (Calendar) for iOS compatibility.
"""

import caldav  # type: ignore
from caldav.elements import dav, cdav  # type: ignore
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from ..config import Config
import uuid
import pytz


class RemindersClient:
    """Apple Calendar client via CalDAV (switched from Reminders to Calendar for iOS compatibility)"""
    
    def __init__(self):
        """Initialize CalDAV client for Apple Calendar"""
        self.client = caldav.DAVClient(
            url=Config.CALDAV_URL,
            username=Config.APPLE_USERNAME,
            password=Config.APPLE_PASSWORD
        )
        self.principal = self.client.principal()
    
    def get_or_create_list(self, list_name: str, color: str = '#007AFF') -> Any:
        """
        Get existing calendar or create new one.
        
        Args:
            list_name: Name of the calendar (e.g., course name)
            color: Hex color for the calendar
            
        Returns:
            CalDAV calendar object
        """
        calendars = self.principal.calendars()
        
        # Try to find existing calendar
        for calendar in calendars:
            try:
                if calendar.name == list_name:
                    return calendar
            except:
                continue
        
        # Create new calendar if not found (now VEVENT instead of VTODO)
        return self.principal.make_calendar(
            name=list_name,
            supported_calendar_component_set=['VEVENT']
        )
    
    def create_reminder(
        self,
        list_name: str,
        title: str,
        notes: str,
        due_date: datetime,
        alarms: List[datetime],
        color: str = '#007AFF',
        course_code: str = None,
        category_label: str = None,
        full_assignment_title: str = None
    ) -> str:
        """
        Create calendar events with alarms.
        Creates main event + dummy events for 48h/24h alarms (iOS limit: 2 alarms/event).
        
        Args:
            list_name: Calendar name
            title: Event title (will be formatted as [LABEL] - course_code)
            notes: Assignment ID for tracking
            due_date: Due date/time
            alarms: List of alarm datetimes (sorted: 48h, 24h, 6h, 2h)
            color: Calendar color
            course_code: Course code for title
            category_label: Category label (e.g., "ASSIGNMENTS")
            full_assignment_title: Full assignment title for notes
            
        Returns:
            Main event UID
        """
        calendar = self.get_or_create_list(list_name, color)
        
        # Format title: [LABEL] - course_code (use calendar_name if available, else course_code, else list_name)
        display_name = course_code or list_name
        formatted_title = f"[{category_label or 'ASSIGNMENT'}] - {display_name}"
        
        # Generate UID
        event_uid = str(uuid.uuid4())
        
        # iOS Calendar supports max 2 alarms per event
        # Create main event with 6h and 2h alarms
        main_alarms = alarms[-2:] if len(alarms) >= 2 else alarms  # Last 2 (6h, 2h)
        
        # Build main VEVENT
        vevent = self._build_vevent(
            uid=event_uid,
            title=formatted_title,
            notes=notes,
            due_date=due_date,
            alarms=main_alarms,
            full_assignment_title=full_assignment_title
        )
        
        # Create main event
        calendar.save_event(vevent)
        
        # Create dummy events for 48h and 24h alarms
        if len(alarms) > 2:
            # 48h alarm (2 days before)
            if len(alarms) >= 4:
                alarm_48h = alarms[0]
                dummy_uid_48h = str(uuid.uuid4())
                dummy_event_48h = self._build_vevent(
                    uid=dummy_uid_48h,
                    title=f"{formatted_title} [48h Alert]",
                    notes=notes,
                    due_date=alarm_48h,  # Event at alarm time
                    alarms=[alarm_48h],  # 1 alarm at event time
                    full_assignment_title=full_assignment_title
                )
                calendar.save_event(dummy_event_48h)
            
            # 24h alarm (1 day before)
            if len(alarms) >= 3:
                alarm_24h = alarms[1]
                dummy_uid_24h = str(uuid.uuid4())
                dummy_event_24h = self._build_vevent(
                    uid=dummy_uid_24h,
                    title=f"{formatted_title} [24h Alert]",
                    notes=notes,
                    due_date=alarm_24h,
                    alarms=[alarm_24h],
                    full_assignment_title=full_assignment_title
                )
                calendar.save_event(dummy_event_24h)
        
        return event_uid
    
    def update_reminder(
        self,
        list_name: str,
        reminder_uid: str,
        title: str,
        notes: str,
        due_date: datetime,
        alarms: List[datetime],
        color: str = '#007AFF',
        course_code: str = None,
        category_label: str = None,
        full_assignment_title: str = None
    ):
        """
        Update existing calendar events (main + dummy alerts).
        
        Args:
            list_name: Calendar name
            reminder_uid: Existing event UID
            title: New title
            notes: New assignment ID
            due_date: New due date
            alarms: New alarm list
            color: Calendar color
            course_code: Course code
            category_label: Category label
            full_assignment_title: Full assignment title
        """
        # Delete old event and all dummy events
        self.delete_reminder(list_name, reminder_uid)
        
        # Recreate with same UID (this will create main + dummy events)
        calendar = self.get_or_create_list(list_name, color)
        
        # Format title
        display_name = course_code or list_name
        formatted_title = f"[{category_label or 'ASSIGNMENT'}] - {display_name}"
        
        # Create main event with 6h and 2h alarms
        main_alarms = alarms[-2:] if len(alarms) >= 2 else alarms
        
        vevent = self._build_vevent(
            uid=reminder_uid,
            title=formatted_title,
            notes=notes,
            due_date=due_date,
            alarms=main_alarms,
            full_assignment_title=full_assignment_title
        )
        
        calendar.save_event(vevent)
        
        # Recreate dummy events for 48h and 24h
        if len(alarms) > 2:
            if len(alarms) >= 4:
                alarm_48h = alarms[0]
                dummy_uid_48h = str(uuid.uuid4())
                dummy_event_48h = self._build_vevent(
                    uid=dummy_uid_48h,
                    title=f"{formatted_title} [48h Alert]",
                    notes=notes,
                    due_date=alarm_48h,
                    alarms=[alarm_48h],
                    full_assignment_title=full_assignment_title
                )
                calendar.save_event(dummy_event_48h)
            
            if len(alarms) >= 3:
                alarm_24h = alarms[1]
                dummy_uid_24h = str(uuid.uuid4())
                dummy_event_24h = self._build_vevent(
                    uid=dummy_uid_24h,
                    title=f"{formatted_title} [24h Alert]",
                    notes=notes,
                    due_date=alarm_24h,
                    alarms=[alarm_24h],
                    full_assignment_title=full_assignment_title
                )
                calendar.save_event(dummy_event_24h)
    
    def delete_reminder(self, list_name: str, reminder_uid: str):
        """
        Delete a calendar event by UID.
        
        Args:
            list_name: Calendar name
            reminder_uid: Event UID to delete
        """
        try:
            calendar = self.get_or_create_list(list_name)
            events = calendar.events()
            
            for event in events:
                if reminder_uid in event.data:
                    event.delete()
                    break
        except Exception as e:
            print(f"Error deleting event {reminder_uid}: {e}")
    
    def find_reminder_by_notes(self, list_name: str, assignment_id: str) -> Optional[str]:
        """
        Find event UID by searching notes for assignment ID.
        Used for recovery if UID is lost.
        
        Args:
            list_name: Calendar name
            assignment_id: Assignment ID to search for
            
        Returns:
            Event UID if found, None otherwise
        """
        try:
            calendar = self.get_or_create_list(list_name)
            events = calendar.events()
            
            for event in events:
                if assignment_id in event.data:
                    # Extract UID from VEVENT
                    for line in event.data.split('\n'):
                        if line.startswith('UID:'):
                            return line.split('UID:')[1].strip()
        except Exception as e:
            print(f"Error searching for event: {e}")
        
        return None
    
    def _build_vevent(
        self,
        uid: str,
        title: str,
        notes: str,
        due_date: datetime,
        alarms: List[datetime],
        full_assignment_title: str = None
    ) -> str:
        """
        Build VEVENT iCalendar format string.
        
        Args:
            uid: Event UID
            title: Event title (concise)
            notes: Assignment ID
            due_date: Due date
            alarms: List of alarm datetimes
            full_assignment_title: Full assignment title for notes
            
        Returns:
            VEVENT string
        """
        # CRITICAL FIX: Convert UTC to IST
        # Google Classroom gives due dates in UTC
        # We need to convert to IST for display
        if due_date.tzinfo is None:
            # If no timezone, assume IST
            due_date = Config.TIMEZONE.localize(due_date)
        else:
            # If has timezone (likely UTC from Google), convert to IST
            due_date = due_date.astimezone(Config.TIMEZONE)
        
        # Format in IST for iCalendar
        due_str = due_date.strftime('%Y%m%dT%H%M%S')
        dtstamp_utc = datetime.now(Config.TIMEZONE).astimezone(pytz.UTC)
        dtstamp_str = dtstamp_utc.strftime('%Y%m%dT%H%M%SZ')
        
        # Build notes: assignment_id + full title
        description_parts = [notes]  # Start with assignment_id
        if full_assignment_title:
            description_parts.append(full_assignment_title)
        description = '; '.join(description_parts)
        
        # For calendar events, use due date as both start and end
        dtstart_str = due_str
        dtend_str = due_str
        
        # Build VEVENT
        vevent_lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//Google Classroom Sync//EN',
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{dtstamp_str}',
            f'DTSTART;TZID=Asia/Kolkata:{dtstart_str}',
            f'DTEND;TZID=Asia/Kolkata:{dtend_str}',
            f'SUMMARY:{title}',
            f'DESCRIPTION:{description}',
            'STATUS:CONFIRMED',
        ]
        
        # Add alarms
        for alarm_time in alarms:
            # Calculate trigger time relative to due date
            trigger_delta = alarm_time - due_date
            trigger_seconds = int(trigger_delta.total_seconds())
            
            # Format as ISO duration (e.g., -PT3600S = 1 hour before)
            trigger_iso = f'-PT{abs(trigger_seconds)}S'
            
            vevent_lines.extend([
                'BEGIN:VALARM',
                'ACTION:DISPLAY',
                f'TRIGGER:{trigger_iso}',
                f'DESCRIPTION:{title}',
                'END:VALARM',
            ])
        
        vevent_lines.extend([
            'END:VEVENT',
            'END:VCALENDAR',
        ])
        
        return '\n'.join(vevent_lines)
