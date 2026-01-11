"""
Main entry point for the sync system.
Handles execution with retry logic and failure alerts.
"""

import sys
import traceback
from datetime import datetime, timedelta
import time
from src.config import Config
from src.database import Database
from src.sync import SyncEngine
from src.utils import EmailAlerter, get_ist_now


def main():
    """
    Main execution function.
    Runs sync with error handling and logging.
    """
    db = Database()
    log_id = None
    
    try:
        # Validate configuration
        Config.validate()
        
        # Create cron log entry
        log_id = db.create_cron_log()
        
        print("🚀 Starting Google Classroom → Apple Reminders Sync")
        print(f"⏰ Timestamp: {get_ist_now().strftime('%Y-%m-%d %I:%M %p IST')}\n")
        
        # Run sync
        engine = SyncEngine()
        stats = engine.sync()
        
        # Update log with success
        db.update_cron_log(log_id, {
            'status': 'SUCCESS',
            **stats
        })
        
        # Record success in failure tracking
        failure_state = db.get_failure_state()
        if failure_state and failure_state.get('consecutive_failures', 0) > 0:
            # Send recovery notification
            alerter = EmailAlerter()
            alerter.send_recovery_notification()
        
        db.record_success()
        
        print("\n✅ Sync completed successfully")
        return 0
        
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"\n❌ Sync failed: {str(e)}")
        print(error_msg)
        
        # Update log with failure
        if log_id:
            db.update_cron_log(log_id, {
                'status': 'FAILED',
                'error_message': error_msg
            })
        
        # Record failure
        consecutive = db.record_failure()
        
        # If this is the second consecutive failure, send alert
        if consecutive >= 2:
            failure_state = db.get_failure_state()
            
            # Only send alert if not already sent
            if not failure_state.get('alert_sent'):
                print("\n📧 Sending failure alert email...")
                alerter = EmailAlerter()
                
                # Try to get GitHub Actions run URL from environment
                github_run_url = None
                import os
                if os.getenv('GITHUB_SERVER_URL') and os.getenv('GITHUB_REPOSITORY') and os.getenv('GITHUB_RUN_ID'):
                    github_run_url = f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
                
                alerter.send_failure_alert(error_msg, github_run_url)
                db.mark_alert_sent()
        
        return 1


def retry_wrapper():
    """
    Wrapper that implements retry logic.
    Retries once after 10 minutes if initial run fails.
    """
    result = main()
    
    if result != 0:
        print("\n🔄 First attempt failed. Retrying in 10 minutes...")
        time.sleep(600)  # Wait 10 minutes
        
        print("\n" + "=" * 60)
        print("RETRY ATTEMPT")
        print("=" * 60 + "\n")
        
        result = main()
        
        if result == 0:
            # Retry succeeded
            db = Database()
            log_id = db.create_cron_log()
            db.update_cron_log(log_id, {
                'status': 'RECOVERED',
                'error_message': 'Recovered after retry'
            })
    
    return result


if __name__ == '__main__':
    sys.exit(retry_wrapper())
