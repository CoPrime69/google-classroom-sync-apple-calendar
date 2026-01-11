# Deployment Checklist

Complete checklist for deploying Google Classroom → Apple Reminders sync.

---

## Pre-Deployment

### 1. Prerequisites ✓

- [ ] Google Classroom account (student)
- [ ] Apple ID with iCloud
- [ ] GitHub account (created)
- [ ] Two-factor authentication enabled on Apple ID
- [ ] 30-60 minutes of uninterrupted time

---

## Service Setup

### 2. Supabase ✓

- [ ] Created account at [supabase.com](https://supabase.com)
- [ ] Created new project
- [ ] Noted project name: `_________________`
- [ ] Copied Project URL: `_________________`
- [ ] Copied anon key: `_________________`
- [ ] Ran `supabase/schema.sql` in SQL Editor
- [ ] Verified tables created in Table Editor:
  - [ ] `courses`
  - [ ] `categories`
  - [ ] `assignments`
  - [ ] `alarms`
  - [ ] `cron_logs`
  - [ ] `cron_failures`

### 3. Google Cloud Console ✓

- [ ] Created/selected project at [console.cloud.google.com](https://console.cloud.google.com)
- [ ] Enabled Google Classroom API
- [ ] Configured OAuth consent screen
- [ ] Added scopes:
  - [ ] `classroom.courses.readonly`
  - [ ] `classroom.coursework.me.readonly`
  - [ ] `classroom.student-submissions.me.readonly`
- [ ] Created OAuth client ID (Desktop app)
- [ ] Downloaded credentials JSON
- [ ] Ran authorization script
- [ ] Obtained refresh token: `_________________`

### 4. Apple ID ✓

- [ ] Logged into [appleid.apple.com](https://appleid.apple.com)
- [ ] Generated app-specific password
- [ ] Labeled: "Classroom Sync"
- [ ] Saved password: `____-____-____-____`

### 5. Resend ✓

- [ ] Created account at [resend.com](https://resend.com)
- [ ] Verified domain OR using onboarding.resend.dev
- [ ] Created API key
- [ ] Saved API key: `re_________________`

---

## Local Testing

### 6. Backend Setup ✓

- [ ] Cloned repository
- [ ] Created `backend/.env` from template
- [ ] Filled in all credentials:
  ```
  SUPABASE_URL=
  SUPABASE_KEY=
  GOOGLE_CLIENT_ID=
  GOOGLE_CLIENT_SECRET=
  GOOGLE_REFRESH_TOKEN=
  APPLE_USERNAME=
  APPLE_PASSWORD=
  CALDAV_URL=https://caldav.icloud.com
  RESEND_API_KEY=
  ALERT_EMAIL=
  TIMEZONE=Asia/Kolkata
  ```
- [ ] Installed dependencies: `pip install -r requirements.txt`
- [ ] Ran credential test: `python test_credentials.py`
- [ ] All tests passed:
  - [ ] Configuration
  - [ ] Supabase
  - [ ] Google Classroom
  - [ ] Apple Reminders
  - [ ] Resend

### 7. Test Sync Locally ✓

- [ ] Ran `python main.py`
- [ ] Checked console output for errors
- [ ] Verified in Supabase:
  - [ ] Courses populated
  - [ ] Categories populated
  - [ ] Assignments created
- [ ] Checked iPhone Reminders app
- [ ] Confirmed reminder lists appeared
- [ ] Confirmed assignments visible

---

## GitHub Deployment

### 8. Repository Setup ✓

- [ ] Pushed code to GitHub (private repo recommended)
- [ ] Went to Settings → Secrets and variables → Actions
- [ ] Added all repository secrets:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_KEY`
  - [ ] `GOOGLE_CLIENT_ID`
  - [ ] `GOOGLE_CLIENT_SECRET`
  - [ ] `GOOGLE_REFRESH_TOKEN`
  - [ ] `APPLE_USERNAME`
  - [ ] `APPLE_PASSWORD`
  - [ ] `CALDAV_URL`
  - [ ] `RESEND_API_KEY`
  - [ ] `ALERT_EMAIL`

### 9. Workflow Testing ✓

- [ ] Went to Actions tab
- [ ] Found "Google Classroom → Apple Reminders Sync" workflow
- [ ] Clicked "Run workflow"
- [ ] Selected branch: `main`
- [ ] Clicked "Run workflow"
- [ ] Waited for completion (1-2 minutes)
- [ ] Checked run logs for errors
- [ ] Verified sync completed successfully

---

## Frontend Deployment

### 10. Vercel Setup ✓

- [ ] Logged into [vercel.com](https://vercel.com)
- [ ] Clicked "New Project"
- [ ] Imported GitHub repository
- [ ] Configured project:
  - [ ] Framework: Next.js (auto-detected)
  - [ ] Root Directory: `frontend`
  - [ ] Build Command: `npm run build`
  - [ ] Output Directory: `.next`
- [ ] Added environment variables:
  - [ ] `NEXT_PUBLIC_SUPABASE_URL`
  - [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] Clicked "Deploy"
- [ ] Waited for deployment (2-3 minutes)
- [ ] Noted deployment URL: `_________________`

### 11. Dashboard Configuration ✓

- [ ] Opened dashboard URL
- [ ] Verified courses loaded
- [ ] Enabled desired courses (toggle buttons)
- [ ] Enabled desired categories within courses
- [ ] Refreshed to confirm changes saved

---

## Verification

### 12. End-to-End Testing ✓

- [ ] Triggered manual workflow run in GitHub Actions
- [ ] Confirmed successful completion
- [ ] Checked Supabase `cron_logs` table
- [ ] Verified `status = 'SUCCESS'`
- [ ] Checked iPhone Reminders app
- [ ] Confirmed reminder lists present
- [ ] Verified assignments with correct:
  - [ ] Titles (with category prefix)
  - [ ] Due dates
  - [ ] Alarm times
- [ ] Waited 5 minutes for iCloud sync

### 13. Cron Schedule ✓

- [ ] Verified workflow file has correct schedule:
  - [ ] `30 6 * * *` (12:00 PM IST)
  - [ ] `30 12 * * *` (06:00 PM IST)
  - [ ] `30 16 * * *` (10:00 PM IST)
- [ ] Confirmed workflow is enabled (not disabled)

---

## Post-Deployment

### 14. Monitoring Setup ✓

- [ ] Added alert email to email client whitelist
- [ ] Checked spam folder settings
- [ ] Set calendar reminder to check system weekly
- [ ] Bookmarked dashboard URL
- [ ] Bookmarked GitHub Actions page

### 15. Documentation Review ✓

- [ ] Read [QUICKSTART.md](docs/QUICKSTART.md)
- [ ] Bookmarked [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [ ] Read [FAQ.md](docs/FAQ.md)
- [ ] Understood assignment lifecycle
- [ ] Understood alarm calculation

---

## Security Check

### 16. Credential Safety ✓

- [ ] Confirmed `.env` in `.gitignore`
- [ ] Verified no credentials in committed code
- [ ] Repository is private (or public without secrets)
- [ ] GitHub secrets are set (not visible in code)
- [ ] Local `.env` file backed up securely
- [ ] Noted where credentials are stored (password manager)

---

## Final Verification

### 17. Deployment Checklist ✓

**All systems operational:**
- [ ] Supabase database accessible
- [ ] Google Classroom API working
- [ ] Apple Reminders syncing
- [ ] Resend emails deliverable
- [ ] GitHub Actions running
- [ ] Frontend dashboard accessible
- [ ] iPhone app showing reminders

**Configuration complete:**
- [ ] Courses enabled in dashboard
- [ ] Categories configured
- [ ] Cron schedule active
- [ ] Email alerts tested (optional)

**Documentation ready:**
- [ ] Setup guide bookmarked
- [ ] Troubleshooting guide accessible
- [ ] Dashboard URL saved

---

## Success Criteria

All checked? **You're deployed!** 🎉

Your automation will now:
- ✅ Sync automatically 3x daily
- ✅ Create reminders for new assignments
- ✅ Update reminders on deadline changes
- ✅ Cancel reminders when submitted
- ✅ Send email alerts on failures
- ✅ Require zero maintenance

---

## Next Steps

1. **Wait for next sync run** (12 PM, 6 PM, or 10 PM IST)
2. **Monitor first few runs** in GitHub Actions
3. **Verify reminders appear** on iPhone
4. **Adjust course/category settings** as needed
5. **Enjoy automated assignment tracking!**

---

## Troubleshooting

If anything fails, see:
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [FAQ.md](docs/FAQ.md)
- GitHub Actions logs
- Supabase Table Editor

---

## Maintenance Schedule

**Weekly:**
- [ ] Check GitHub Actions runs
- [ ] Verify reminders are current

**Monthly:**
- [ ] Review Supabase usage
- [ ] Check for missed assignments
- [ ] Update course/category settings

**As Needed:**
- [ ] Regenerate OAuth tokens (every 6 months)
- [ ] Update dependencies
- [ ] Add new courses

---

**Deployment Status**: ⏳ **IN PROGRESS** / ✅ **COMPLETE**

**Deployed By**: `_________________`

**Deployment Date**: `_________________`

**Dashboard URL**: `_________________`

**Notes**:
```
_____________________________________________________________

_____________________________________________________________

_____________________________________________________________
```

---

Congratulations on deploying your production automation system! 🚀
