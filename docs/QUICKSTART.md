# Quick Start

Get up and running in under 30 minutes.

---

## Prerequisites Checklist

- [ ] Google Classroom account
- [ ] Apple ID with iCloud
- [ ] GitHub account
- [ ] 30 minutes of time

---

## Step-by-Step Setup

### 1. Clone and Setup (5 min)

```bash
# Clone repository
git clone <your-repo-url>
cd project_self

# Create local environment file
cd backend
cp .env.example .env
```

### 2. Supabase Setup (5 min)

1. Create account at [supabase.com](https://supabase.com)
2. Create new project
3. Copy project URL and anon key to `.env`:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJhbG...
   ```
4. Run schema:
   - Open SQL Editor
   - Paste contents of `supabase/schema.sql`
   - Click Run

### 3. Google Classroom (10 min)

1. Enable API at [console.cloud.google.com](https://console.cloud.google.com)
2. Create OAuth credentials
3. Run this Python script to get refresh token:

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly'
]

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',  # Download from Google Cloud Console
    scopes=SCOPES
)

creds = flow.run_local_server(port=0)
print(f"Refresh Token: {creds.refresh_token}")
```

4. Add to `.env`:
   ```
   GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
   GOOGLE_REFRESH_TOKEN=1//xxxxx
   ```

### 4. Apple Reminders (3 min)

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Security → App-Specific Passwords
3. Generate password
4. Add to `.env`:
   ```
   APPLE_USERNAME=your-email@icloud.com
   APPLE_PASSWORD=xxxx-xxxx-xxxx-xxxx
   CALDAV_URL=https://caldav.icloud.com
   ```

### 5. Resend Email (3 min)

1. Sign up at [resend.com](https://resend.com)
2. Create API key
3. Verify domain OR use onboarding.resend.dev (easier for personal use)
4. Add to `.env`:
   ```
   RESEND_API_KEY=re_xxxxx
   ALERT_EMAIL=your-email@example.com
   ```

### 6. Test Locally (2 min)

```bash
# Install dependencies
pip install -r requirements.txt

# Test credentials
python test_credentials.py
```

Expected output:
```
✅ PASS: Configuration
✅ PASS: Supabase
✅ PASS: Google Classroom
✅ PASS: Apple Reminders
✅ PASS: Resend
```

### 7. Deploy to GitHub (2 min)

```bash
# Push to GitHub
git add .
git commit -m "Initial setup"
git push origin main
```

Add all credentials as **Repository Secrets**:
- Settings → Secrets and variables → Actions
- Add each variable from `.env`

### 8. Run First Sync (1 min)

1. Go to Actions tab
2. Click "Google Classroom → Apple Reminders Sync"
3. Run workflow
4. Wait for completion (1-2 minutes)

### 9. Configure Dashboard (2 min)

1. Deploy frontend to Vercel:
   - Import GitHub repo
   - Root directory: `frontend`
   - Add environment variables
2. Open dashboard URL
3. Enable courses you want to monitor
4. Toggle categories

### 10. Verify on iPhone (1 min)

1. Open Reminders app
2. Look for course lists
3. Check for assignments with alarms

---

## ✅ You're Done!

Your automation is now running. Sync happens automatically:
- 12:00 PM IST
- 06:00 PM IST
- 10:00 PM IST

---

## Next Steps

- Review [SETUP.md](SETUP.md) for detailed configuration
- Check [ARCHITECTURE.md](ARCHITECTURE.md) to understand how it works
- Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if issues arise

---

## Common First-Time Issues

**No courses showing?**
- Wait for first sync to complete
- Check GitHub Actions logs

**No reminders on iPhone?**
- Verify iCloud sync is enabled
- Wait 5-10 minutes for sync
- Check Settings → Reminders → iCloud

**Workflow failing?**
- Run `test_credentials.py` locally
- Verify all GitHub secrets are set
- Check error in Actions logs

---

Enjoy your automated reminder system! 🎉
