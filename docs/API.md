# API Reference

Complete API documentation for all modules in the sync system.

---

## Configuration (`src/config.py`)

### `Config`

Central configuration class that loads environment variables.

#### Class Attributes

```python
Config.SUPABASE_URL: str           # Supabase project URL
Config.SUPABASE_KEY: str           # Supabase anon key
Config.GOOGLE_CLIENT_ID: str       # OAuth client ID
Config.GOOGLE_CLIENT_SECRET: str   # OAuth client secret
Config.GOOGLE_REFRESH_TOKEN: str   # OAuth refresh token
Config.APPLE_USERNAME: str         # Apple ID email
Config.APPLE_PASSWORD: str         # App-specific password
Config.CALDAV_URL: str             # CalDAV server URL
Config.RESEND_API_KEY: str         # Resend API key
Config.ALERT_EMAIL: str            # Alert recipient email
Config.TIMEZONE: pytz.timezone     # Asia/Kolkata timezone
Config.NOTIFICATION_START_HOUR: int # 7 (no alerts before 7 AM)
Config.NOTIFICATION_END_HOUR: int  # 24 (midnight)
Config.ALARM_INTERVALS: List[int]  # [48, 24, 6, 2] hours
```

#### Methods

```python
@classmethod
Config.validate() -> bool
```
Validates all required environment variables are set.

**Raises**: `ValueError` if any required variables are missing.

---

## Database (`src/database/db.py`)

### `Database`

Supabase database interface for all CRUD operations.

#### Constructor

```python
Database()
```
Initializes Supabase client using config credentials.

#### Course Methods

```python
get_enabled_courses() -> List[Dict[str, Any]]
```
Returns all courses where `enabled = True`.

```python
upsert_course(course_data: Dict[str, Any]) -> Dict[str, Any]
```
Insert or update a course. Returns the course record.

**Parameters**:
- `course_data`: Dictionary with keys: `id`, `name`, `section`, `description`, `enabled`, `color`

```python
get_course(course_id: str) -> Optional[Dict[str, Any]]
```
Get a specific course by ID.

#### Category Methods

```python
get_enabled_categories(course_id: str) -> List[Dict[str, Any]]
```
Returns all enabled categories for a course.

```python
upsert_category(category_data: Dict[str, Any]) -> Dict[str, Any]
```
Insert or update a category.

**Parameters**:
- `category_data`: Dictionary with keys: `id`, `course_id`, `name`, `enabled`

```python
get_category(category_id: str) -> Optional[Dict[str, Any]]
```
Get a specific category by ID.

#### Assignment Methods

```python
get_assignment(assignment_id: str) -> Optional[Dict[str, Any]]
```
Get a specific assignment by ID.

```python
get_active_assignments() -> List[Dict[str, Any]]
```
Returns all assignments where `is_dead = False`.

```python
upsert_assignment(assignment_data: Dict[str, Any]) -> Dict[str, Any]
```
Insert or update an assignment. Auto-updates `updated_at`.

**Parameters**:
- `assignment_data`: Dictionary with keys: `id`, `course_id`, `category_id`, `title`, `description`, `due_date`, `submission_status`, `is_dead`, `reminder_uid`

```python
mark_assignment_dead(assignment_id: str)
```
Marks assignment as dead (no further processing).

```python
update_submission_status(assignment_id: str, status: str)
```
Updates submission status and last_checked timestamp.

**Parameters**:
- `status`: `'SUBMITTED'` or `'NOT_SUBMITTED'`

```python
update_due_date(assignment_id: str, new_due_date: str)
```
Updates both `due_date` and `last_seen_due_date` when deadline extension detected.

**Parameters**:
- `new_due_date`: ISO 8601 timestamp string

```python
mark_submission_checked_post_deadline(assignment_id: str)
```
Marks `submission_checked_post_deadline = True` to prevent repeated checks.

**Note**: `upsert_assignment()` automatically:
- Sets `last_seen_due_date = due_date` on first insert
- Generates `reminder_notes_fingerprint` from assignment ID and course ID

#### Alarm Methods

```python
get_alarms(assignment_id: str) -> List[Dict[str, Any]]
```
Get all alarms for an assignment.

```python
upsert_alarm(alarm_data: Dict[str, Any]) -> Dict[str, Any]
```
Insert or update an alarm.

**Parameters**:
- `alarm_data`: Dictionary with keys: `assignment_id`, `alarm_type`, `scheduled_time`, `fired`

```python
mark_alarm_fired(assignment_id: str, alarm_type: str)
```
Marks alarm as fired with timestamp.

```python
delete_alarms(assignment_id: str)
```
Deletes all alarms for an assignment.

#### Cron Logging Methods

```python
create_cron_log() -> int
```
Creates new cron log entry. Returns log ID.

```python
update_cron_log(log_id: int, update_data: Dict[str, Any])
```
Updates cron log with completion data.

**Parameters**:
- `update_data`: Dictionary with keys: `status`, `error_message`, `assignments_processed`, `reminders_created`, `reminders_updated`, `reminders_cancelled`

#### Failure Tracking Methods

```python
get_failure_state() -> Dict[str, Any]
```
Returns current failure tracking record.

```python
record_success()
```
Records successful run, resets failure counter.

```python
record_failure() -> int
```
Increments failure counter. Returns consecutive failure count.

```python
mark_alert_sent()
```
Marks that failure alert email has been sent.

---

## Google Classroom (`src/classroom/client.py`)

### `ClassroomClient`

Google Classroom API client with OAuth authentication.

#### Constructor

```python
ClassroomClient()
```
Initializes Classroom API service with refresh token credentials.

#### Methods

```python
get_courses() -> List[Dict[str, Any]]
```
Fetches all active courses.

**Returns**: List of normalized course dictionaries with keys:
- `id`: Course ID
- `name`: Course name
- `section`: Section (optional)
- `description`: Description (optional)

```python
get_course_topics(course_id: str) -> List[Dict[str, Any]]
```
Fetches all topics/categories for a course.

**Parameters**:
- `course_id`: Google Classroom course ID

**Returns**: List of topic dictionaries with keys:
- `id`: Topic ID
- `course_id`: Parent course ID
- `name`: Topic name

```python
get_coursework(course_id: str) -> List[Dict[str, Any]]
```
Fetches all coursework assignments for a course.

**Parameters**:
- `course_id`: Google Classroom course ID

**Returns**: List of coursework dictionaries with keys:
- `id`: Assignment ID
- `course_id`: Parent course ID
- `category_id`: Topic ID (optional)
- `title`: Assignment title
- `description`: Assignment description
- `due_date`: ISO datetime string (IST timezone)

```python
get_submission_status(course_id: str, coursework_id: str) -> str
```
Gets submission status for an assignment.

**Parameters**:
- `course_id`: Course ID
- `coursework_id`: Assignment ID

**Returns**: `'SUBMITTED'` or `'NOT_SUBMITTED'`

---

## Apple Reminders (`src/reminders/client.py`)

### `RemindersClient`

Apple Reminders client using CalDAV protocol.

#### Constructor

```python
RemindersClient()
```
Initializes CalDAV client for iCloud reminders.

#### Methods

```python
get_or_create_list(list_name: str, color: str = '#007AFF') -> Calendar
```
Gets existing reminder list or creates new one.

**Parameters**:
- `list_name`: Name of reminder list (e.g., course name)
- `color`: Hex color code for list

**Returns**: CalDAV calendar object

```python
create_reminder(
    list_name: str,
    title: str,
    notes: str,
    due_date: datetime,
    alarms: List[datetime],
    color: str = '#007AFF'
) -> str
```
Creates new reminder with multiple alarms.

**Parameters**:
- `list_name`: Target reminder list name
- `title`: Reminder title (with category prefix)
- `notes`: Reminder notes (contains assignment ID)
- `due_date`: Due date/time
- `alarms`: List of alarm datetimes
- `color`: List color

**Returns**: Reminder UID

```python
update_reminder(
    list_name: str,
    reminder_uid: str,
    title: str,
    notes: str,
    due_date: datetime,
    alarms: List[datetime],
    color: str = '#007AFF'
)
```
Updates existing reminder (deletes and recreates with same UID).

**Parameters**: Same as `create_reminder` plus `reminder_uid`

```python
delete_reminder(list_name: str, reminder_uid: str)
```
Deletes a reminder by UID.

```python
find_reminder_by_notes(list_name: str, assignment_id: str) -> Optional[str]
```
Finds reminder UID by searching notes for assignment ID.

**Returns**: Reminder UID if found, None otherwise

---

## Sync Engine (`src/sync/engine.py`)

### `SyncEngine`

Core synchronization orchestrator.

#### Constructor

```python
SyncEngine()
```
Initializes database, classroom, and reminders clients.

#### Methods

```python
sync() -> Dict[str, int]
```
Executes complete sync cycle.

**Returns**: Statistics dictionary with keys:
- `assignments_processed`: Number of assignments checked
- `reminders_created`: Number of new reminders
- `reminders_updated`: Number of updated reminders
- `reminders_cancelled`: Number of cancelled reminders

**Process**:
1. Sync courses and categories from Classroom
2. Get enabled courses and categories
3. Process each enabled course
4. For each assignment:
   - Check if new or existing
   - Check submission status
   - Check for deadline extensions
   - Create/update/cancel reminders
5. Return statistics

---

## Utilities (`src/utils/`)

### DateTime Utils (`datetime_utils.py`)

```python
calculate_alarms(
    due_date: datetime,
    current_time: datetime = None
) -> List[datetime]
```
Calculates alarm times based on due date.

**Returns**: List of alarm datetimes (48h, 24h, 6h, 2h before)

```python
apply_time_window(dt: datetime) -> datetime
```
Applies notification time window (no alerts before 7 AM).

```python
is_deadline_extended(old_due: datetime, new_due: datetime) -> bool
```
Checks if deadline was extended.

```python
is_past_deadline(due_date: datetime, current_time: datetime = None) -> bool
```
Checks if assignment deadline has passed.

```python
format_category_title(
    category_name: str,
    assignment_title: str,
    course_name: str = None
) -> str
```
Formats reminder title with category prefix.

**Example**: `"[LAB] Oscilloscope Experiment – PHY204"`

```python
get_ist_now() -> datetime
```
Returns current time in IST timezone.

```python
parse_iso_datetime(iso_string: str) -> datetime
```
Parses ISO datetime string to timezone-aware datetime.

### Email Alerter (`email_alerter.py`)

```python
class EmailAlerter:
    def __init__(self)
    def send_failure_alert(error_message: str, workflow_run_url: str = None)
    def send_recovery_notification()
```

Sends email alerts via Resend.

---

## Main Entry Point (`main.py`)

### Functions

```python
main() -> int
```
Main execution function with error handling and logging.

**Returns**: 0 for success, 1 for failure

**Process**:
1. Validate configuration
2. Create cron log
3. Run sync engine
4. Update log with results
5. Handle failures and send alerts

```python
retry_wrapper() -> int
```
Wrapper with retry logic.

**Process**:
1. Run `main()`
2. If fails, wait 10 minutes
3. Retry once
4. Send alert if both fail

---

## Frontend API

### Supabase Client

Frontend uses `@supabase/supabase-js` to directly query:

- `courses` table: Enable/disable courses
- `categories` table: Enable/disable categories

No backend API needed - direct database access with RLS.

---

## Error Handling

All functions handle errors with:

1. **Try-catch blocks** with error logging
2. **Database transaction rollbacks** on failure
3. **Email alerts** on critical failures
4. **Graceful degradation** (skip failing items, continue processing)

---

## Rate Limits

- **Google Classroom API**: 1000 requests/100 seconds
- **CalDAV**: No official limit (reasonable use)
- **Supabase**: Free tier limits (monitor usage)
- **Resend**: 100 emails/day, 3000/month (free tier)

---

This API reference covers all public interfaces in the system. For internal implementation details, see source code comments.
