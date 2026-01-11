# Architecture Documentation

Technical architecture of the Google Classroom → Apple Reminders sync system.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions                          │
│  Cron: 12 PM, 6 PM, 10 PM IST                               │
│  - Stateless execution                                       │
│  - Automatic retry on failure                                │
│  - Email alerts on double failure                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Python Sync Engine                        │
│  - Fetch from Google Classroom API                           │
│  - Apply course & category filters                           │
│  - Calculate alarm times                                     │
│  - Manage assignment lifecycle                               │
└─────────────────┬───────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│  Supabase    │    │ Apple iCloud │
│  (State)     │    │  (CalDAV)    │
└──────────────┘    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   iPhone     │
                    │  Reminders   │
                    └──────────────┘
```

---

## Component Architecture

### 1. **Backend (Python)**

#### File Structure

```
backend/
├── src/
│   ├── config.py              # Configuration management
│   ├── classroom/
│   │   ├── __init__.py
│   │   └── client.py          # Google Classroom API
│   ├── reminders/
│   │   ├── __init__.py
│   │   └── client.py          # Apple CalDAV client
│   ├── database/
│   │   ├── __init__.py
│   │   └── db.py              # Supabase interface
│   ├── sync/
│   │   ├── __init__.py
│   │   └── engine.py          # Core sync logic
│   └── utils/
│       ├── __init__.py
│       ├── datetime_utils.py  # Time calculations
│       └── email_alerter.py   # Resend integration
├── main.py                    # Entry point with retry
└── requirements.txt
```

#### Key Classes

**SyncEngine** (`sync/engine.py`)
- Orchestrates entire sync process
- Manages assignment lifecycle
- Coordinates between all clients

**ClassroomClient** (`classroom/client.py`)
- OAuth authentication with refresh tokens
- Fetches courses, coursework, topics
- Checks submission status

**RemindersClient** (`reminders/client.py`)
- CalDAV protocol for Apple Reminders
- Creates/updates/deletes VTODO items
- Manages reminder lists and alarms

**Database** (`database/db.py`)
- Supabase PostgreSQL interface
- State persistence and queries
- Cron logging and failure tracking

---

### 2. **Database (Supabase/PostgreSQL)**

#### Schema

**courses**
```sql
id TEXT PRIMARY KEY
name TEXT
section TEXT
description TEXT
enabled BOOLEAN DEFAULT FALSE
color TEXT DEFAULT '#007AFF'
created_at TIMESTAMP
updated_at TIMESTAMP
```

**categories**
```sql
id TEXT PRIMARY KEY
course_id TEXT FK → courses(id)
name TEXT
enabled BOOLEAN DEFAULT TRUE
created_at TIMESTAMP
updated_at TIMESTAMP
UNIQUE(course_id, name)
```

**assignments**
```sql
id TEXT PRIMARY KEY
course_id TEXT FK → courses(id)
category_id TEXT FK → categories(id)
title TEXT
description TEXT
due_date TIMESTAMP WITH TIME ZONE
last_seen_due_date TIMESTAMP WITH TIME ZONE  -- Track deadline changes
submission_status TEXT DEFAULT 'NOT_SUBMITTED'
submission_checked_post_deadline BOOLEAN DEFAULT FALSE  -- One-time final check
is_dead BOOLEAN DEFAULT FALSE
reminder_uid TEXT
reminder_notes_fingerprint TEXT  -- Recovery mechanism
category_name TEXT  -- Denormalized for historical context
last_checked TIMESTAMP
created_at TIMESTAMP
updated_at TIMESTAMP

-- Performance index
CREATE INDEX idx_assignments_active ON assignments(course_id, category_id, is_dead)
WHERE is_dead = false;
```

**alarms**
```sql
id SERIAL PRIMARY KEY
assignment_id TEXT FK → assignments(id)
alarm_type TEXT ('48h', '24h', '6h', '2h')
scheduled_time TIMESTAMP WITH TIME ZONE
fired BOOLEAN DEFAULT FALSE
fired_at TIMESTAMP
created_at TIMESTAMP
UNIQUE(assignment_id, alarm_type)
```

**cron_logs**
```sql
id SERIAL PRIMARY KEY
started_at TIMESTAMP
completed_at TIMESTAMP
status TEXT ('SUCCESS', 'FAILED', 'RETRY', 'RECOVERED')
error_message TEXT
assignments_processed INTEGER
reminders_created INTEGER
reminders_updated INTEGER
reminders_cancelled INTEGER
```

**cron_failures**
```sql
id SERIAL PRIMARY KEY
last_success TIMESTAMP
consecutive_failures INTEGER
last_failure TIMESTAMP
alert_sent BOOLEAN
updated_at TIMESTAMP
```

---

### 3. **Frontend (Next.js + React)**

#### File Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Dashboard page
│   │   └── globals.css        # Tailwind styles
│   └── lib/
│       └── supabase.ts        # Supabase client
├── package.json
├── next.config.js
├── tailwind.config.js
└── tsconfig.json
```

#### Features

- **Course Management**: Enable/disable course monitoring
- **Category Filters**: Toggle categories per course
- **Real-time Updates**: Direct Supabase queries
- **Responsive UI**: Tailwind CSS styling

---

## Data Flow

### Sync Execution Flow

```
1. GitHub Actions Trigger (Cron)
   ↓
2. Load Configuration (Config.validate())
   ↓
3. Create Cron Log (db.create_cron_log())
   ↓
4. Sync Courses & Categories
   - classroom.get_courses()
   - classroom.get_course_topics()
   - db.upsert_course()
   - db.upsert_category()
   ↓
5. Get Enabled Courses (db.get_enabled_courses())
   ↓
6. For each enabled course:
   ↓
   a. Get enabled categories
   ↓
   b. Fetch coursework (classroom.get_coursework())
   ↓
   c. For each assignment:
      - Check if exists in DB
      - If new → create reminder
      - If existing → check for updates:
        * Submission status
        * Deadline extension
        * Category change
        * Past deadline
   ↓
7. Update Cron Log with stats
   ↓
8. Record success/failure in cron_failures
   ↓
9. Send email alert if needed
```

---

## Assignment Lifecycle

```
NEW
 │
 ├─→ [Course enabled?] ──No──→ IGNORED
 │
 ├─→ [Category enabled?] ──No──→ IGNORED
 │
 ├─→ [Has due date?] ──No──→ IGNORED
 │
 └─→ [Past deadline?] ──Yes──→ IGNORED
     │
     No
     ↓
   ACTIVE
     │
     ├─→ [Submitted?] ──Yes──→ DEAD (cancelled)
     │
     ├─→ [Deadline extended?] ──Yes──→ REACTIVATED (updated)
     │
     ├─→ [Category changed?] ──Yes──→ UPDATED
     │
     └─→ [Past deadline?] ──Yes──→ DEAD (final check)
```

---

## Alarm Calculation Logic

### Default Intervals

- 48 hours before due date
- 24 hours before due date
- 6 hours before due date
- 2 hours before due date

### Time Window Constraints

```python
def apply_time_window(alarm_time):
    # No notifications before 7 AM
    if alarm_time.hour < 7:
        return alarm_time.replace(hour=7, minute=0)
    
    # Notifications allowed until midnight
    return alarm_time
```

### Example Calculation

**Assignment due: Feb 10, 2026 11:59 PM**

```
48h alarm → Feb 8, 11:59 PM ✓
24h alarm → Feb 9, 11:59 PM ✓
6h alarm  → Feb 10, 5:59 PM ✓
2h alarm  → Feb 10, 9:59 PM ✓
```

**Assignment due: Feb 10, 2026 6:00 AM**

```
48h alarm → Feb 8, 6:00 AM → clamped to 7:00 AM ✓
24h alarm → Feb 9, 6:00 AM → clamped to 7:00 AM ✓
6h alarm  → Feb 10, 12:00 AM → clamped to 7:00 AM ✓
2h alarm  → Feb 10, 4:00 AM → clamped to 7:00 AM ✓
```

---

## Failure Handling

### Retry Logic

```
Run 1 → FAIL
  ↓
Wait 10 minutes
  ↓
Run 2 (retry) → SUCCESS → Status: RECOVERED
              ↓
              FAIL → Send Email Alert
```

### Email Alert Conditions

1. **Consecutive failures ≥ 2**
2. **Alert not already sent**

### Recovery Detection

- Next successful run resets failure counter
- Sends recovery notification email
- Backfills any missed assignments (state-driven)

---

## Security

### Credential Storage

| Credential | Storage | Access |
|------------|---------|--------|
| Supabase URL/Key | GitHub Secrets | Actions only |
| Google OAuth | GitHub Secrets | Actions only |
| Apple Password | GitHub Secrets | Actions only |
| Resend API Key | GitHub Secrets | Actions only |
| Frontend Env Vars | Vercel | Public (anon key) |

### Data Access

- **Supabase RLS**: Enabled with allow-all policies (single-user)
- **Frontend**: Read/write courses and categories only
- **Backend**: Full access to all tables

---

## Performance Optimizations

1. **State-Driven Processing**
   - Only active assignments are checked
   - Dead assignments never reprocessed
   - Submitted assignments immediately skipped

2. **Efficient API Usage**
   - Batch course fetching with pagination
   - Submission checks only for active assignments
   - CalDAV updates use UID-based matching

3. **Database Indexing**
   - Index on `is_dead` for quick filtering
   - Index on `due_date` for deadline checks
   - Composite indexes on foreign keys

---

## Monitoring & Observability

### Logs

- **GitHub Actions**: Full execution logs with timestamps
- **Supabase cron_logs**: Historical run data
- **Email Alerts**: Critical failure notifications

### Metrics Tracked

- Assignments processed
- Reminders created
- Reminders updated
- Reminders cancelled
- Consecutive failures
- Last successful run

---

## Scaling Considerations

### Current Limits (Free Tier)

- **Supabase**: 500 MB database, 2 GB bandwidth/month
- **GitHub Actions**: 2000 minutes/month
- **Resend**: 100 emails/day, 3000/month
- **Vercel**: Unlimited bandwidth

### Future Improvements

1. **Multi-user support**
   - Add user authentication
   - Row-level security by user
   - Separate reminder lists per user

2. **Notion integration**
   - Sync to Notion database
   - Bidirectional updates

3. **Advanced filtering**
   - Per-assignment ignore
   - Temporary mute periods
   - Priority levels

---

## Testing Strategy

### Unit Tests

- Alarm calculation logic
- Time window constraints
- Lifecycle state transitions

### Integration Tests

- Google Classroom API mocking
- CalDAV protocol testing
- Database operations

### End-to-End Tests

- Full sync with test data
- Failure recovery scenarios
- Email alerting

---

## Deployment Checklist

- [ ] Supabase project created and schema loaded
- [ ] Google OAuth credentials configured
- [ ] Apple app-specific password generated
- [ ] Resend API key created and domain verified
- [ ] GitHub repository secrets set
- [ ] Frontend deployed to Vercel
- [ ] Test run successful
- [ ] Email alerts verified
- [ ] iPhone sync confirmed

---

This architecture enables **production-grade personal automation** with reliability, maintainability, and zero operational overhead.
