# FAQ (Frequently Asked Questions)

---

## General Questions

### What does this system do?

Automatically syncs Google Classroom assignments to Apple Reminders with:
- Course and category filtering
- Submission-aware notifications
- Deadline extension handling
- Time-windowed alerts (7 AM - midnight)
- Multi-alarm reminders (48h, 24h, 6h, 2h)
- Automatic failure alerts via email

### How often does it sync?

Three times daily at:
- 12:00 PM IST
- 06:00 PM IST
- 10:00 PM IST

### Is my data safe?

Yes. The system:
- Runs on your private GitHub repository
- Uses OAuth for Google (read-only access)
- Uses app-specific password for Apple (isolated access)
- Stores data in your private Supabase instance
- Never shares data with third parties

### Does it cost money?

No, using free tiers:
- GitHub Actions: 2000 minutes/month (plenty for this)
- Supabase: 500 MB database (enough for years)
- Resend: 100 emails/day, 3000/month (you'll use ~1/month)
- Vercel: Unlimited bandwidth

### Can I use this with multiple Google accounts?

Not currently. The system is designed for single-user use. Multi-user support would require:
- User authentication
- Per-user credential storage
- Row-level security

---

## Setup Questions

### Do I need to know how to code?

Basic familiarity helps, but step-by-step guides are provided. You'll need to:
- Run Python scripts (copy-paste commands)
- Configure environment variables
- Use GitHub web interface

### What if I don't have a Mac/iPhone?

You need an iPhone or iPad for Apple Reminders. The sync runs on GitHub Actions (cloud), not your computer.

### Can I test it without deploying?

Yes! Run locally:
```bash
cd backend
pip install -r requirements.txt
python test_credentials.py  # Test credentials
python main.py              # Run sync
```

### How do I get the Google refresh token?

See [SETUP.md](SETUP.md) section 2. You'll run a Python script that opens your browser and gets the token.

### What if my app-specific password doesn't work?

Common issues:
- Used regular password instead of app-specific
- Copied password with extra spaces
- Two-factor authentication not enabled (required)

Regenerate and try again.

---

## Usage Questions

### How do I enable/disable courses?

1. Open frontend dashboard (Vercel URL)
2. Click toggle button next to course name
3. Changes apply on next sync run

### What happens if I submit an assignment?

On next sync:
1. System detects submission
2. Cancels future alarms
3. Marks assignment as "dead" (no further processing)
4. Deletes reminder from Apple Reminders

### What if a professor extends a deadline?

On next sync:
1. System detects new due date
2. Recalculates alarm times
3. Updates existing reminder (doesn't create new one)
4. New alarms are scheduled

### Can I manually add/remove reminders?

Not recommended. The system manages reminders automatically. Manual changes may be overwritten.

### What if I want to mute a specific assignment?

Currently not supported. You can:
- Disable the category it belongs to
- Disable the entire course
- Manually delete the reminder (but it'll be recreated on next sync)

---

## Technical Questions

### Why CalDAV and not direct Apple Reminders API?

Apple doesn't provide a public Reminders API. CalDAV is the official protocol for iCloud calendar/reminder sync.

### Why GitHub Actions and not a server?

Benefits:
- Free and reliable
- No server maintenance
- Automatic scaling
- Built-in logging
- Secure secret storage

### What happens if sync fails?

1. First failure: Automatic retry after 10 minutes
2. Second failure: Email alert sent to you
3. Next successful run: Backfills any missed assignments

### How does it handle rate limits?

- Google Classroom: 1000 requests/100 seconds (we use ~10/run)
- CalDAV: No official limit, reasonable use
- Supabase: 50 requests/second (we use ~20/run)

### Can I change the sync schedule?

Yes, edit `.github/workflows/sync.yml`:
```yaml
schedule:
  - cron: '30 6 * * *'   # 12:00 PM IST
  - cron: '30 12 * * *'  # 06:00 PM IST
  - cron: '30 16 * * *'  # 10:00 PM IST
```

Convert IST to UTC (IST = UTC + 5:30).

### What database does it use?

Supabase (PostgreSQL). All state is stored there:
- Courses and categories
- Assignments and their status
- Reminder UIDs
- Sync logs and failure tracking

---

## Troubleshooting Questions

### No reminders appearing on iPhone?

1. Check iCloud sync: Settings → Apple ID → iCloud → Reminders
2. Wait 5-10 minutes for sync
3. Verify workflow succeeded in GitHub Actions
4. Check `assignments` table in Supabase

### Reminders keep duplicating?

Usually caused by:
- Lost reminder UIDs (CalDAV connection issue)
- Manual deletion of reminders

Fix:
1. Check `assignments.reminder_uid` in Supabase
2. Delete duplicate lists in Apple Reminders
3. Re-run sync

### Workflow failing with "Unauthorized"?

Check which service:
- **Supabase**: Verify URL and key
- **Google**: Regenerate refresh token
- **Apple**: Regenerate app-specific password
- **Resend**: Check API key and domain verification

### Categories not showing?

Google Classroom must have "Topics" created. In Classroom:
1. Go to Classwork
2. Create → Topic
3. Assign coursework to topics

### Alarms firing at wrong times?

Verify timezone is `Asia/Kolkata` in:
- `backend/.env` (local)
- GitHub Actions workflow
- Supabase should store UTC with timezone info

---

## Feature Questions

### Can I sync to Notion instead of Reminders?

Not currently implemented, but architecture supports it:
1. Create `NotionClient` similar to `RemindersClient`
2. Modify `SyncEngine` to call both
3. Add Notion credentials

### Can I get notifications on other devices?

Apple Reminders syncs to all devices signed into your iCloud:
- iPhone
- iPad
- Mac
- Apple Watch

### Can I customize alarm times?

Yes, edit `Config.ALARM_INTERVALS` in `src/config.py`:
```python
ALARM_INTERVALS = [72, 48, 24, 12, 6, 2]  # hours before due
```

### Can I filter by assignment type (quiz vs homework)?

Not directly, but you can:
- Use category filtering (topics)
- Modify `ClassroomClient` to check `workType` field

### Can I see grades/marks?

Not implemented. System only tracks:
- Assignment existence
- Due dates
- Submission status

---

## Privacy & Security Questions

### What data is stored?

- **Supabase**: Course names, assignment titles, due dates, submission status
- **GitHub**: Encrypted credentials in secrets
- **Apple iCloud**: Reminders with assignment info

### Who can access my data?

Only you. All components use your personal accounts:
- Private GitHub repo
- Your Supabase instance
- Your Apple ID
- Your Resend account

### What permissions does it need?

- **Google Classroom**: Read-only access to courses and assignments
- **Apple iCloud**: Full Reminders access (via CalDAV)
- **Supabase**: Full database access
- **Resend**: Send emails from verified domain

### Can I revoke access?

Yes:
- **Google**: [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
- **Apple**: [appleid.apple.com](https://appleid.apple.com) → Security → App-Specific Passwords
- **Supabase**: Delete project
- **Resend**: Revoke API key

---

## Advanced Questions

### Can I run this on my own server?

Yes, with modifications:
1. Replace GitHub Actions with cron job
2. Set environment variables on server
3. Run `python main.py` on schedule

### Can I add custom processing logic?

Yes, modify `SyncEngine._process_assignment()`:
```python
def _process_assignment(self, coursework, course):
    # Your custom logic here
    if "urgent" in coursework['title'].lower():
        # Create additional alarm
        pass
```

### Can I integrate with other services?

Yes, create new client classes:
- `SlackClient` for notifications
- `TrelloClient` for card creation
- `CalendarClient` for Google Calendar events

### How do I contribute?

1. Fork repository
2. Create feature branch
3. Make changes
4. Submit pull request

---

## Support Questions

### Where do I get help?

1. Read documentation:
   - [SETUP.md](SETUP.md)
   - [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
   - [ARCHITECTURE.md](ARCHITECTURE.md)

2. Check GitHub Actions logs for errors

3. Review Supabase tables for data issues

4. Open GitHub issue with:
   - Problem description
   - Error messages
   - Steps to reproduce

### How do I report a bug?

Open GitHub issue with:
- Clear title
- Expected behavior
- Actual behavior
- Error messages
- GitHub Actions logs (if relevant)

### Can I request features?

Yes! Open GitHub issue with:
- Feature description
- Use case
- Why it's useful

---

## Maintenance Questions

### Do I need to update anything?

Occasionally:
- Regenerate Google refresh token (every 6 months)
- Rotate Apple app-specific password (as needed)
- Update Python dependencies (`pip install --upgrade -r requirements.txt`)

### How do I backup my data?

Supabase provides automatic backups. To export:
1. Supabase dashboard → Table Editor
2. Select table → Export as CSV

### What if I want to stop using it?

1. Disable GitHub Actions workflow
2. Delete Supabase project
3. Revoke Google OAuth access
4. Revoke Apple app-specific password
5. Delete Apple Reminder lists manually

### How do I monitor health?

- Check email for failure alerts
- Review GitHub Actions runs weekly
- Check `cron_logs` table in Supabase

---

Still have questions? Open a GitHub issue!
