"""
Google Classroom API integration.
Handles authentication and fetching courses, assignments, and submission status.

Required OAuth Scopes (Student Account):
- https://www.googleapis.com/auth/classroom.courses.readonly
- https://www.googleapis.com/auth/classroom.coursework.me (NOT .readonly!)
- https://www.googleapis.com/auth/classroom.student-submissions.me.readonly
- https://www.googleapis.com/auth/classroom.topics.readonly
"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Dict, Optional, Any
from datetime import datetime
import pytz
from ..config import Config


class ClassroomClient:
    """Google Classroom API client"""
    
    def __init__(self):
        """Initialize Classroom API client with OAuth credentials"""
        creds = Credentials(
            token=None,
            refresh_token=Config.GOOGLE_REFRESH_TOKEN,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=Config.GOOGLE_CLIENT_ID,
            client_secret=Config.GOOGLE_CLIENT_SECRET
        )
        
        self.service = build('classroom', 'v1', credentials=creds)
    
    def get_courses(self) -> List[Dict[str, Any]]:
        """
        Fetch all active courses.
        Returns list of course dictionaries.
        """
        courses = []
        page_token = None
        
        while True:
            response = (self.service.courses()
                       .list(pageToken=page_token, courseStates=['ACTIVE'])
                       .execute())
            
            courses.extend(response.get('courses', []))
            page_token = response.get('nextPageToken')
            
            if not page_token:
                break
        
        return [self._normalize_course(course) for course in courses]
    
    def get_course_topics(self, course_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all topics (categories) for a course.
        Returns list of topic dictionaries.
        """
        try:
            response = (self.service.courses().topics()
                       .list(courseId=course_id)
                       .execute())
            
            topics = response.get('topic', [])
            return [self._normalize_topic(topic, course_id) for topic in topics]
        except Exception as e:
            print(f"Error fetching topics for course {course_id}: {e}")
            return []
    
    def get_coursework(self, course_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all coursework (assignments) for a course.
        Returns list of coursework dictionaries.
        """
        try:
            response = (self.service.courses().courseWork()
                       .list(courseId=course_id)
                       .execute())
            
            coursework = response.get('courseWork', [])
            return [self._normalize_coursework(cw, course_id) for cw in coursework]
        except Exception as e:
            print(f"Error fetching coursework for course {course_id}: {e}")
            return []
    
    def get_submission_status(self, course_id: str, coursework_id: str) -> str:
        """
        Get submission status for a specific assignment.
        Returns: 'SUBMITTED' or 'NOT_SUBMITTED'
        """
        try:
            # Get student submissions for this coursework
            response = (self.service.courses().courseWork().studentSubmissions()
                       .list(courseId=course_id, courseWorkId=coursework_id, userId='me')
                       .execute())
            
            submissions = response.get('studentSubmissions', [])
            
            if not submissions:
                return 'NOT_SUBMITTED'
            
            # Check the first submission (there should only be one per student)
            submission = submissions[0]
            state = submission.get('state', 'NEW')
            
            # Map Google Classroom states to our simplified states
            #   TURNED_IN, RETURNED          -> SUBMITTED
            #   RECLAIMED_BY_STUDENT, NEW   -> NOT_SUBMITTED (unsubmitted)
            if state in ['TURNED_IN', 'RETURNED']:
                return 'SUBMITTED'
            else:
                return 'NOT_SUBMITTED'
                
        except Exception as e:
            print(f"Error fetching submission for {coursework_id}: {e}")
            return 'NOT_SUBMITTED'
    
    def _normalize_course(self, course: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize course data to our schema"""
        return {
            'id': course['id'],
            'name': course.get('name', 'Untitled Course'),
            'section': course.get('section'),
            'description': course.get('descriptionHeading'),
        }
    
    def _normalize_topic(self, topic: Dict[str, Any], course_id: str) -> Dict[str, Any]:
        """Normalize topic data to our schema"""
        return {
            'id': topic['topicId'],
            'course_id': course_id,
            'name': topic.get('name', 'Untitled Topic'),
        }
    
    def _normalize_coursework(self, coursework: Dict[str, Any], course_id: str) -> Dict[str, Any]:
        """Normalize coursework data to our schema"""
        # Parse due date
        due_date = None
        if 'dueDate' in coursework:
            due_info = coursework['dueDate']
            time_info = coursework.get('dueTime', {})
            
            year = due_info.get('year')
            month = due_info.get('month')
            day = due_info.get('day')
            hour = time_info.get('hours', 23)
            minute = time_info.get('minutes', 59)
            
            if year and month and day:
                # Google returns dueDate/dueTime in the course's timezone, but
                # in practice for this setup it behaves like UTC. To ensure
                # Classroom's wall-clock time (e.g. 11 PM) matches the
                # student's IST calendar, interpret the raw time as UTC and
                # convert to our configured timezone (Asia/Kolkata).
                naive_dt = datetime(year, month, day, hour, minute, 0)
                dt_utc = naive_dt.replace(tzinfo=pytz.UTC)
                due_date = dt_utc.astimezone(Config.TIMEZONE)
        
        return {
            'id': coursework['id'],
            'course_id': course_id,
            'category_id': coursework.get('topicId'),
            'title': coursework.get('title', 'Untitled Assignment'),
            'description': coursework.get('description'),
            'due_date': due_date.isoformat() if due_date else None,
        }
