# Troubleshooting Guide

Common issues and solutions for Google Classroom → Apple Reminders sync.

---

## 🔍 Debugging Workflow

### 1. Check GitHub Actions Logs

1. Go to your repository → **Actions** tab
2. Click on latest workflow run
3. Expand "Run sync" step
4. Look for errors or warnings

### 2. Check Supabase Tables

1. Open Supabase dashboard
2. Go to **Table Editor**
3. Check:
   - `courses`: Are courses present?
   - `categories`: Are categories present and enabled?
   - `assignments`: Are assignments being created?
   - `cron_logs`: What's the status of recent runs?

### 3. Check Email Alerts

- Look in inbox for failure alerts
- Check spam folder
- Verify alert email in Resend dashboard

---

## ❌ Common Issues

### Issue: "No courses appearing in database"

**Symptoms**:
- Frontend shows "No Courses Found"
- `courses` table is empty

**Possible Causes**:

1. **Invalid Google OAuth credentials**
   - Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
   - Check `GOOGLE_REFRESH_TOKEN` is correct
   
2. **Missing OAuth scopes**
   - Required scopes:
     ```
     classroom.courses.readonly
     classroom.coursework.me.readonly
     classroom.student-submissions.me.readonly
     ```
   
3. **Workflow not run yet**
   - Manually trigger workflow
   - Wait for scheduled run

**Solution**:
1. Regenerate refresh token with correct scopes
2. Update GitHub secrets
3. Run workflow manually

---

### Issue: "Reminders not appearing in Apple Reminders app"

**Symptoms**:
- No reminder lists on iPhone
- Assignments in database but no reminders

**Possible Causes**:

1. **Invalid Apple credentials**
   - Check `APPLE_USERNAME` (full email)
   - Verify `APPLE_PASSWORD` (app-specific password)
   
2. **iCloud sync disabled**
   - Reminders sync disabled on iPhone
   - iCloud account not signed in

3. **CalDAV connection issues**
   - Wrong `CALDAV_URL` (should be `https://caldav.icloud.com`)
   - Network/firewall blocking CalDAV

**Solution**:

1. Verify credentials:
   ```python
   # Test CalDAV connection locally
   import caldav
   client = caldav.DAVClient(
       url='https://caldav.icloud.com',
       username='your-email@icloud.com',
       password='xxxx-xxxx-xxxx-xxxx'
   )
   principal = client.principal()
   calendars = principal.calendars()
   print(f"Found {len(calendars)} calendars")
   ```

2. iPhone settings:
   - Settings → Apple ID → iCloud → Reminders → ON
   - Wait 5-10 minutes for sync

3. Regenerate app-specific password if needed

---

### Issue: "Workflow failing with 'Missing required environment variables'"

**Symptoms**:
- Workflow fails immediately
- Error message lists missing variables

**Solution**:

1. Go to repository Settings → Secrets and variables → Actions
2. Verify all secrets are set:
   ```
   SUPABASE_URL
   SUPABASE_KEY
   GOOGLE_CLIENT_ID
   GOOGLE_CLIENT_SECRET
   GOOGLE_REFRESH_TOKEN
   APPLE_USERNAME
   APPLE_PASSWORD
   CALDAV_URL
   RESEND_API_KEY
   ALERT_EMAIL
   ```
3. Check for typos in secret names
4. Re-run workflow

---

### Issue: "Assignment submitted but reminder still active"

**Symptoms**:
- Assignment marked as submitted in Classroom
- Reminder still shows with alarms

**Possible Causes**:

1. **Sync hasn't run yet**
   - Wait for next scheduled run (12 PM, 6 PM, 10 PM IST)
   
2. **Course/category disabled**
   - Assignment won't be checked if course disabled

**Solution**:
- Manually trigger workflow
- Check that course is enabled in dashboard
- Verify assignment appears in `assignments` table with updated `submission_status`

---

### Issue: "Email alerts not received"

**Symptoms**:
- Workflow failing but no email alert
- Email alert expected but not received

**Possible Causes**:

1. **Resend API key invalid**
   - Key expired or revoked
   
2. **Sender domain not verified**
   - Resend requires domain verification or use onboarding.resend.dev
   
3. **Less than 2 consecutive failures**
   - Alert only sent after 2 failures

4. **Alert already sent**
   - Only one alert per failure period

**Solution**:

1. Verify Resend API key:
   - Log into Resend dashboard
   - API Keys section
   - Check key is active

2. Verify domain or use onboarding domain:
   - For personal use, can use onboarding.resend.dev
   - Or verify your own domain in Domains section

3. Check spam folder

4. Check `cron_failures` table:
   ```sql
   SELECT * FROM cron_failures;
   ```

---

### Issue: "Lost Reminder UIDs in Database"

**Symptoms**:
- `reminder_uid` is NULL in assignments table
- Console shows "Reminder UID not found, creating new"

**Recovery**:

The system uses `reminder_notes_fingerprint` for automatic recovery:

1. Check database state:
   ```sql
   SELECT id, title, reminder_uid, reminder_notes_fingerprint
   FROM assignments
   WHERE reminder_uid IS NULL AND is_dead = false;
   ```

2. System automatically attempts recovery:
   - First tries `find_reminder_by_notes()` with fingerprint
   - Falls back to assignment ID search
   - Creates new reminder if recovery fails

3. Manual fingerprint format:
   ```
   classroom_assignment_id={assignment_id};course_id={course_id}
   ```

---

### Issue: "Duplicate Rows in cron_failures Table"

**Symptoms**:
- Multiple rows in `cron_failures` table
- Inconsistent failure counting

**Solution**:

The table enforces singleton pattern with `CHECK (id = 1)`:

```sql
-- Delete all rows
DELETE FROM cron_failures;

-- Re-insert singleton row
INSERT INTO cron_failures (id, consecutive_failures, last_success_at)
VALUES (1, 0, NOW())
ON CONFLICT (id) DO NOTHING;
```

---

### Issue: "Post-Deadline Submission Checks Repeating"

**Symptoms**:
- Multiple submission API calls after deadline
- Rate limit warnings from Google Classroom API

**Diagnosis**:

```sql
SELECT id, title, due_date, submission_checked_post_deadline
FROM assignments
WHERE due_date < NOW() AND is_dead = false;
```

**Solution**:

The `submission_checked_post_deadline` flag ensures only ONE final check:

1. System automatically sets flag after first post-deadline check
2. Manual reset if needed:
   ```sql
   UPDATE assignments
   SET submission_checked_post_deadline = false
   WHERE id = 'assignment_id';
   ```

---

### Issue: "Deadline extended but alarms not updated"

**Symptoms**:
- Professor extended deadline
- Old alarms still firing

**Possible Causes**:

1. **Classroom not updated yet**
   - Classroom API hasn't reflected new deadline
   
2. **Due date format issue**
   - Classroom API returns inconsistent date formats

**Solution**:
- Wait for next sync run
- Check `assignments` table for updated `due_date`
- Verify in GitHub Actions logs that extension was detected

---

### Issue: "Supabase connection failed"

**Symptoms**:
- Workflow fails with database errors
- "Connection refused" or "Unauthorized" errors

**Possible Causes**:

1. **Invalid Supabase credentials**
   - Wrong URL or key
   
2. **Supabase project paused**
   - Free tier projects pause after inactivity
   
3. **Network issues**
   - GitHub Actions network restrictions

**Solution**:

1. Verify credentials:
   - Supabase dashboard → Settings → API
   - Copy URL and anon key
   - Update GitHub secrets

2. Unpause project:
   - Open Supabase dashboard
   - Click "Restore" if paused

---

### Issue: "Categories not appearing for course"

**Symptoms**:
- Course has categories in Classroom
- Dashboard shows "No categories found"

**Possible Causes**:

1. **Topics not created in Classroom**
   - Assignments not organized into topics
   
2. **Classroom API permissions**
   - Missing topic read permissions

**Solution**:

1. Check Google Classroom:
   - Open course → Classwork
   - Verify topics exist
   
2. Create topics in Classroom:
   - Click "Create" → "Topic"
   - Assign coursework to topics

3. Re-run sync

---

### Issue: "Timezone issues - alarms at wrong time"

**Symptoms**:
- Alarms firing at unexpected times
- Times don't match IST

**Solution**:

- Verify `TIMEZONE=Asia/Kolkata` in GitHub Actions workflow
- Check system is using IST for calculations
- All times stored in database should be IST

---

### Issue: "Too many reminders / duplicates"

**Symptoms**:
- Multiple reminders for same assignment
- Old reminders not cleaned up

**Possible Causes**:

1. **UID tracking lost**
   - `reminder_uid` not stored correctly
   
2. **Reminder deletion failed**
   - CalDAV delete operation failed

**Solution**:

1. Check `assignments` table:
   ```sql
   SELECT id, title, reminder_uid FROM assignments WHERE is_dead = false;
   ```

2. Manually delete duplicate lists in Apple Reminders

3. Clear and re-sync (advanced):
   ```sql
   -- Backup first!
   DELETE FROM assignments;
   DELETE FROM categories;
   DELETE FROM courses;
   ```

---

## 🛠️ Advanced Debugging

### Run Sync Locally

1. Clone repository
2. Create `backend/.env`:
   ```
   SUPABASE_URL=...
   SUPABASE_KEY=...
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REFRESH_TOKEN=...
   APPLE_USERNAME=...
   APPLE_PASSWORD=...
   CALDAV_URL=...
   RESEND_API_KEY=...
   ALERT_EMAIL=...
   TIMEZONE=Asia/Kolkata
   ```

3. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. Run sync:
   ```bash
   python main.py
   ```

5. Check detailed output and errors

### Test Individual Components

**Test Google Classroom:**
```python
from src.classroom import ClassroomClient

client = ClassroomClient()
courses = client.get_courses()
print(f"Found {len(courses)} courses")

for course in courses:
    coursework = client.get_coursework(course['id'])
    print(f"{course['name']}: {len(coursework)} assignments")
```

**Test Apple Reminders:**
```python
from src.reminders import RemindersClient
from datetime import datetime, timedelta

client = RemindersClient()
due = datetime.now() + timedelta(days=2)
alarms = [due - timedelta(hours=24)]

uid = client.create_reminder(
    list_name='Test',
    title='Test Reminder',
    notes='Test assignment',
    due_date=due,
    alarms=alarms
)
print(f"Created reminder: {uid}")
```

**Test Database:**
```python
from src.database import Database

db = Database()
courses = db.get_enabled_courses()
print(f"Enabled courses: {len(courses)}")
```

---

## 📧 Getting Help

If none of these solutions work:

1. **Check GitHub Actions logs** for detailed error messages
2. **Review Supabase logs** in dashboard
3. **Test credentials** individually
4. **Open GitHub issue** with:
   - Error message
   - Steps to reproduce
   - Relevant log excerpts
   - Configuration (without credentials)

---

## 🔄 Reset Everything (Nuclear Option)

If system is completely broken:

1. **Delete all Supabase data:**
   ```sql
   TRUNCATE TABLE alarms CASCADE;
   TRUNCATE TABLE assignments CASCADE;
   TRUNCATE TABLE categories CASCADE;
   TRUNCATE TABLE courses CASCADE;
   TRUNCATE TABLE cron_logs CASCADE;
   UPDATE cron_failures SET consecutive_failures = 0, alert_sent = false;
   ```

2. **Delete Apple Reminder lists:**
   - Open Reminders app
   - Delete all course lists manually

3. **Re-run workflow:**
   - Everything will be recreated from scratch

---

This guide covers 95% of common issues. For edge cases, review source code and API documentation.
