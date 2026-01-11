# Backend Scripts

Essential utility scripts for maintenance and debugging.

## Available Scripts

### Maintenance
- `delete_assignments.py` - Delete all assignments from database (for cleanup/reset)
- `cleanup_calendar.py` - Delete calendars from Apple CalDAV (for cleanup/reset)

### Verification
- `verify_config.py` - Verify database configuration and course settings

### Database
- `migration_add_course_fields.sql` - SQL migration for adding course_code, calendar_name, and sync_without_categories fields

## Usage

Run any script from the backend root:
```bash
cd backend
python scripts/delete_assignments.py
python scripts/cleanup_calendar.py
python scripts/verify_config.py
```

## When to Use

- **After making database changes**: Run `verify_config.py` to confirm settings
- **Before fresh sync**: Run `delete_assignments.py` and `cleanup_calendar.py` to reset, then `python main.py`
- **Database setup**: Apply `migration_add_course_fields.sql` if needed

