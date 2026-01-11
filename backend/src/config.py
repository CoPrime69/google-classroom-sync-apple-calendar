"""
Configuration management for the sync system.
Loads environment variables and provides centralized config access.
"""

import os
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

class Config:
    """Central configuration class"""
    
    # Supabase
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Google Classroom
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
    
    # Apple Reminders
    APPLE_USERNAME = os.getenv('APPLE_USERNAME')
    APPLE_PASSWORD = os.getenv('APPLE_PASSWORD')
    CALDAV_URL = os.getenv('CALDAV_URL', 'https://caldav.icloud.com')
    
    # Email Alerts
    RESEND_API_KEY = os.getenv('RESEND_API_KEY')
    ALERT_EMAIL = os.getenv('ALERT_EMAIL')
    
    # Timezone
    TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Kolkata'))
    
    # Notification Time Window
    NOTIFICATION_START_HOUR = int(os.getenv('NOTIFICATION_START_HOUR', 7))
    NOTIFICATION_END_HOUR = int(os.getenv('NOTIFICATION_END_HOUR', 24))
    
    # Alarm intervals (in hours)
    ALARM_INTERVALS = [48, 24, 6, 2]
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            'SUPABASE_URL',
            'SUPABASE_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET',
            'GOOGLE_REFRESH_TOKEN',
            'APPLE_USERNAME',
            'APPLE_PASSWORD',
            'RESEND_API_KEY',
            'ALERT_EMAIL'
        ]
        
        missing = [var for var in required if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True
