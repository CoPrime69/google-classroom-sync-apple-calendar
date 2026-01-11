"""
Email alerting via Resend.
Sends failure alerts when cron execution fails.
"""

import resend
from datetime import datetime
from ..config import Config


class EmailAlerter:
    """Email alert sender"""
    
    def __init__(self):
        resend.api_key = Config.RESEND_API_KEY
        self.from_email = 'onboarding@resend.dev'
        self.to_email = Config.ALERT_EMAIL
    
    def send_failure_alert(self, error_message: str, workflow_run_url: str = None):
        """
        Send failure alert email.
        
        Args:
            error_message: Error details
            workflow_run_url: GitHub Actions run URL
        """
        subject = '🚨 Google Classroom Sync Failed'
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #d32f2f;">Sync Workflow Failed</h2>
            
            <p><strong>Timestamp:</strong> {datetime.now(Config.TIMEZONE).strftime('%Y-%m-%d %I:%M %p IST')}</p>
            
            <h3>Error Details</h3>
            <pre style="background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto;">
{error_message}
            </pre>
            
            {f'<p><a href="{workflow_run_url}" style="color: #1976d2;">View GitHub Actions Logs</a></p>' if workflow_run_url else ''}
            
            <hr style="margin: 30px 0;">
            
            <h3>What This Means</h3>
            <ul>
                <li>The sync workflow failed twice (initial run + retry)</li>
                <li>Your reminders may not be up to date</li>
                <li>The next successful run will backfill any missed assignments</li>
            </ul>
            
            <h3>Next Steps</h3>
            <ol>
                <li>Check the GitHub Actions logs for details</li>
                <li>Verify your API credentials are still valid</li>
                <li>If the issue persists, check Supabase and iCloud connectivity</li>
            </ol>
            
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated alert from your Google Classroom → Apple Reminders sync system.
            </p>
        </body>
        </html>
        """
        
        try:
            params = {
                "from": self.from_email,
                "to": [self.to_email],
                "subject": subject,
                "html": html_content
            }
            resend.Emails.send(params)
            print(f"Failure alert sent successfully")
        except Exception as e:
            print(f"Failed to send alert email: {e}")
    
    def send_recovery_notification(self):
        """Send notification when sync recovers after failures"""
        subject = '✅ Google Classroom Sync Recovered'
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #388e3c;">Sync Workflow Recovered</h2>
            
            <p><strong>Timestamp:</strong> {datetime.now(Config.TIMEZONE).strftime('%Y-%m-%d %I:%M %p IST')}</p>
            
            <p>The sync workflow is now running successfully again.</p>
            
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated notification from your Google Classroom → Apple Reminders sync system.
            </p>
        </body>
        </html>
        """
        
        try:
            params = {
                "from": self.from_email,
                "to": [self.to_email],
                "subject": subject,
                "html": html_content
            }
            resend.Emails.send(params)
            print(f"Recovery notification sent successfully")
        except Exception as e:
            print(f"Failed to send recovery notification: {e}")
