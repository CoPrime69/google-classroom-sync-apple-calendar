# System Diagrams

Visual representations of the Google Classroom → Apple Reminders sync system.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER                                      │
│  ┌──────────────┐              ┌──────────────┐                │
│  │   iPhone     │◄─────────────┤   Dashboard  │                │
│  │  Reminders   │   iCloud     │   (Vercel)   │                │
│  └──────────────┘              └──────────────┘                │
└───────┬──────────────────────────────┬───────────────────────────┘
        │                              │
        │ Sync                         │ Configure
        │                              │
┌───────▼──────────────────────────────▼───────────────────────────┐
│                     CLOUD INFRASTRUCTURE                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              GitHub Actions (Cron)                       │   │
│  │  • Runs 3x daily (12 PM, 6 PM, 10 PM IST)               │   │
│  │  • Stateless execution                                   │   │
│  │  • Automatic retry on failure                            │   │
│  └────────────┬────────────────────────────────┬────────────┘   │
│               │                                │                 │
│        Fetch  │                         Update │                 │
│               │                                │                 │
│  ┌────────────▼────────┐          ┌───────────▼──────────┐     │
│  │  Google Classroom   │          │  Apple iCloud        │     │
│  │       API           │          │     CalDAV           │     │
│  │  • Courses          │          │  • Create reminders  │     │
│  │  • Assignments      │          │  • Update reminders  │     │
│  │  • Submissions      │          │  • Delete reminders  │     │
│  └─────────────────────┘          └──────────────────────┘     │
│               │                                │                 │
│               └────────────┬───────────────────┘                 │
│                            │                                     │
│                   ┌────────▼─────────┐                          │
│                   │    Supabase      │                          │
│                   │  (PostgreSQL)    │                          │
│                   │  • State storage │                          │
│                   │  • Sync logs     │                          │
│                   │  • Configuration │                          │
│                   └──────────────────┘                          │
│                            │                                     │
│                   On Failure                                     │
│                            │                                     │
│                   ┌────────▼─────────┐                          │
│                   │     Resend       │                          │
│                   │  Email Alert     │                          │
│                   └──────────────────┘                          │
└───────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    SYNC EXECUTION FLOW                        │
└──────────────────────────────────────────────────────────────┘

1. TRIGGER
   │
   ├─ Cron: 12 PM IST
   ├─ Cron: 6 PM IST
   ├─ Cron: 10 PM IST
   └─ Manual: GitHub Actions UI
   │
   ▼
2. FETCH COURSES
   │
   └─► Google Classroom API
       │
       └─► Store in Supabase
   │
   ▼
3. GET ENABLED COURSES
   │
   └─► Query: SELECT * FROM courses WHERE enabled = true
   │
   ▼
4. FOR EACH ENABLED COURSE
   │
   ├─► Fetch Coursework
   │   └─► Google Classroom API
   │
   ├─► Fetch Topics/Categories
   │   └─► Google Classroom API
   │
   ├─► Get Enabled Categories
   │   └─► Query: SELECT * FROM categories WHERE enabled = true
   │
   └─► FOR EACH ASSIGNMENT
       │
       ├─► Is Submitted?
       │   └─► Google Classroom API (submission status)
       │       │
       │       ├─ YES ─► Mark dead + Delete reminder
       │       │
       │       └─ NO ──┐
       │               │
       ├─► Is Past Deadline?
       │   │
       │   ├─ YES ─► Mark dead + Delete reminder
       │   │
       │   └─ NO ──┐
       │           │
       ├─► Deadline Extended?
       │   │
       │   ├─ YES ─► Update reminder + Recalculate alarms
       │   │
       │   └─ NO ──┐
       │           │
       ├─► Category Changed?
       │   │
       │   ├─ YES ─► Update reminder title
       │   │
       │   └─ NO ──┐
       │           │
       └─► Is New?
           │
           ├─ YES ─► Create reminder
           │         │
           │         ├─► Calculate alarms (48h, 24h, 6h, 2h)
           │         ├─► Apply time window (no before 7 AM)
           │         ├─► Create in Apple Reminders
           │         └─► Store UID in Supabase
           │
           └─ NO ──► No action
   │
   ▼
5. UPDATE LOGS
   │
   └─► INSERT INTO cron_logs (status, stats)
   │
   ▼
6. CHECK FOR FAILURES
   │
   ├─ SUCCESS ─► Reset failure counter
   │
   └─ FAILURE ─┐
              │
              ├─► Retry after 10 minutes
              │   │
              │   ├─ SUCCESS ─► Mark as RECOVERED
              │   │
              │   └─ FAILURE ─► Send email alert
              │
              └─► UPDATE cron_failures
```

---

## Assignment Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                  ASSIGNMENT STATE MACHINE                    │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │  DISCOVERED  │
                    │  (from API)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         No Course    No Category   No Due Date
          Enabled      Enabled
              │            │            │
              └────────────┴────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   IGNORED    │
                    └──────────────┘


                    ┌──────────────┐
                    │     NEW      │
                    │ (First seen) │
                    └──────┬───────┘
                           │
                           ├─► Create Reminder
                           ├─► Store in DB
                           └─► Calculate Alarms
                           │
                           ▼
                    ┌──────────────┐
                    │    ACTIVE    │
                    │ (Monitored)  │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          │                │                │
     Submitted      Deadline Ext.    Past Deadline
          │                │                │
          │                │                │
          ▼                ▼                ▼
   ┌──────────┐    ┌──────────────┐  ┌──────────┐
   │   DEAD   │    │ REACTIVATED  │  │   DEAD   │
   │(Submitted)│    │ (Updated)    │  │(Expired) │
   └──────────┘    └──────┬───────┘  └──────────┘
          │                │                │
          │                │                │
          └────────► Cancel Reminder ◄──────┘
                    Delete Alarms
                    Mark is_dead = true
```

---

## Database Schema

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE DATABASE                         │
└─────────────────────────────────────────────────────────────┘

courses
├─ id (PK)
├─ name
├─ section
├─ description
├─ enabled ◄──────────── Dashboard controls
├─ color
├─ created_at
└─ updated_at

       │
       │ 1:N
       ▼
categories
├─ id (PK)
├─ course_id (FK) ──────► courses.id
├─ name
├─ enabled ◄──────────── Dashboard controls
├─ created_at
└─ updated_at

       │
       │ 1:N
       ▼
assignments
├─ id (PK)
├─ course_id (FK) ──────► courses.id
├─ category_id (FK) ────► categories.id
├─ title
├─ description
├─ due_date
├─ submission_status
├─ is_dead ◄──────────── Lifecycle control
├─ reminder_uid ◄──────── Apple Reminders link
├─ last_checked
├─ created_at
└─ updated_at

       │
       │ 1:N
       ▼
alarms
├─ id (PK)
├─ assignment_id (FK) ──► assignments.id
├─ alarm_type (48h, 24h, 6h, 2h)
├─ scheduled_time
├─ fired
├─ fired_at
└─ created_at


cron_logs (Audit trail)
├─ id (PK)
├─ started_at
├─ completed_at
├─ status
├─ error_message
├─ assignments_processed
├─ reminders_created
├─ reminders_updated
└─ reminders_cancelled


cron_failures (Failure tracking)
├─ id (PK)
├─ last_success
├─ consecutive_failures
├─ last_failure
├─ alert_sent
└─ updated_at
```

---

## Component Interaction

```
┌─────────────────────────────────────────────────────────────┐
│                  COMPONENT DIAGRAM                           │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                         main.py                               │
│  • Entry point                                                │
│  • Retry wrapper                                              │
│  • Error handling                                             │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        │ Uses
                        ▼
           ┌────────────────────────┐
           │     SyncEngine         │
           │  • Orchestrates sync   │
           │  • Manages lifecycle   │
           │  • Coordinates clients │
           └────────┬───────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│Classroom │ │Reminders │ │ Database │
│  Client  │ │  Client  │ │  Client  │
└──────────┘ └──────────┘ └──────────┘
     │             │             │
     │             │             │
     ▼             ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│  Google  │ │  Apple   │ │ Supabase │
│Classroom │ │ CalDAV   │ │   API    │
└──────────┘ └──────────┘ └──────────┘


         ┌────────────────────────┐
         │      utils/            │
         │  • datetime_utils      │
         │  • email_alerter       │
         └────────────────────────┘
                    ▲
                    │ Uses
                    │
           ┌────────┴───────┐
           │                │
    ┌──────────┐    ┌──────────┐
    │SyncEngine│    │ main.py  │
    └──────────┘    └──────────┘
```

---

## Time Window Logic

```
┌─────────────────────────────────────────────────────────────┐
│              ALARM TIME CALCULATION                          │
└─────────────────────────────────────────────────────────────┘

Due: Feb 10, 2026 11:59 PM
│
├─► 48h alarm = Feb 8, 11:59 PM ✓ (within window)
├─► 24h alarm = Feb 9, 11:59 PM ✓ (within window)
├─► 6h alarm  = Feb 10, 5:59 PM ✓ (within window)
└─► 2h alarm  = Feb 10, 9:59 PM ✓ (within window)


Due: Feb 10, 2026 6:00 AM
│
├─► 48h alarm = Feb 8, 6:00 AM → CLAMPED to 7:00 AM
├─► 24h alarm = Feb 9, 6:00 AM → CLAMPED to 7:00 AM
├─► 6h alarm  = Feb 10, 12:00 AM → CLAMPED to 7:00 AM
└─► 2h alarm  = Feb 10, 4:00 AM → CLAMPED to 7:00 AM


Time Window Rules:
┌─────────────────────────────────────────┐
│  7 AM ◄────── Allowed ──────► 12 AM    │
│  (Earliest)              (Latest)       │
└─────────────────────────────────────────┘

Before 7 AM  → Clamp to 7:00 AM
After 12 AM  → Allowed (for late deadlines)
```

---

These diagrams visualize the complete system architecture and data flow.
