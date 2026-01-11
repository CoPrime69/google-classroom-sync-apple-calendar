# Setup Guide

Complete setup instructions for Google Classroom → Apple Reminders automation.

---

## 📋 Prerequisites

- Google Classroom account (student)
- Apple ID with iCloud
- GitHub account
- Supabase account (free tier)
- Resend account (free tier)

---

## 1️⃣ Supabase Setup

### Create Project

1. Go to [supabase.com](https://supabase.com)
2. Click "New Project"
3. Choose organization and name your project
4. Set a strong database password
5. Select region closest to you
6. Wait for project to be provisioned

### Run Database Schema

1. In Supabase dashboard, go to **SQL Editor**
2. Click "New Query"
3. Copy entire contents of `supabase/schema.sql`
4. Paste and click "Run"
5. Verify all tables are created in **Table Editor**

### Get API Credentials

1. Go to **Settings** → **API**
2. Copy:
   - **Project URL** (save as `SUPABASE_URL`)
   - **anon public** key (save as `SUPABASE_KEY`)

---

## 2️⃣ Google Classroom API Setup

### Enable Google Classroom API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Enable **Google Classroom API**:
   - Go to **APIs & Services** → **Library**
   - Search "Google Classroom API"
   - Click **Enable**

### Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Configure consent screen if prompted:
   - User Type: **External**
   - App name: "Classroom Sync"
   - Add your email as developer
   - Scopes: Add these 3 scopes only:
     - `https://www.googleapis.com/auth/classroom.courses.readonly`
     - `https://www.googleapis.com/auth/classroom.coursework.me`
     - `https://www.googleapis.com/auth/classroom.student-submissions.me.readonly`
4. Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: "Classroom Sync Client"
5. Download credentials JSON

### Get Refresh Token

Run this Python script locally to get your refresh token:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
import json

# IMPORTANT: Only request minimal scopes needed for student account
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me',  # No .readonly suffix!
    'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly'
]

# Use your downloaded credentials
flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    scopes=SCOPES
)

creds = flow.run_local_server(port=0)

print(f"Client ID: {creds.client_id}")
print(f"Client Secret: {creds.client_secret}")
print(f"Refresh Token: {creds.refresh_token}")
```

Save:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

---

## 3️⃣ Apple Reminders Setup

### Generate App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in with your Apple ID
3. Go to **Security** → **App-Specific Passwords**
4. Click **Generate an app-specific password**
5. Label: "Classroom Sync"
6. Copy the generated password (16 characters with hyphens)

### Save Credentials

- `APPLE_USERNAME`: Your full Apple ID email
- `APPLE_PASSWORD`: The app-specific password
- `CALDAV_URL`: `https://caldav.icloud.com` (default)

---

## 4️⃣ Resend Email Setup

### Create Resend Account

1. Go to [resend.com](https://resend.com)
2. Sign up for free tier (100 emails/day, 3000/month)
3. Verify your email address

### Add & Verify Domain (or use onboarding domain)

**Option 1: Use Your Domain (Recommended)**
1. Go to **Domains** → **Add Domain**
2. Enter your domain (e.g., `yourdomain.com`)
3. Add DNS records (SPF, DKIM, DMARC) to your domain registrar
4. Wait for verification (usually instant)

**Option 2: Use Resend's Onboarding Domain (Quick Start)**
1. Resend provides `onboarding.resend.dev` for testing
2. Can send to your own verified email only
3. Perfect for personal projects

### Create API Key

1. Go to **API Keys**
2. Click **Create API Key**
3. Name: "Classroom Sync Alerts"
4. Permission: **Sending access**
5. Copy API key (save as `RESEND_API_KEY`)

### Configure Alert Email

- If using your own domain: `ALERT_EMAIL=noreply@yourdomain.com`
- If using onboarding domain: `ALERT_EMAIL=your-verified-email@gmail.com`

**Note**: With onboarding domain, emails can only be sent to your verified email address.

---

## 5️⃣ GitHub Repository Setup

### Create Repository

1. Create new **private** repository on GitHub
2. Clone this project to the repository
3. Push all code

### Configure Secrets

Go to **Settings** → **Secrets and variables** → **Actions**

Add the following repository secrets:

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbG...
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_REFRESH_TOKEN=1//xxxxx
APPLE_USERNAME=your-email@icloud.com
APPLE_PASSWORD=xxxx-xxxx-xxxx-xxxx
CALDAV_URL=https://caldav.icloud.com
RESEND_API_KEY=re_xxxxx
ALERT_EMAIL=noreply@yourdomain.com
```

### Enable GitHub Actions

1. Go to **Actions** tab
2. Enable workflows if prompted
3. Workflow will run on schedule automatically

---

## 6️⃣ Frontend Dashboard Setup (Vercel)

### Deploy to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repository
3. Configure project:
   - Framework: **Next.js**
   - Root Directory: `frontend`
4. Add environment variables:
   ```
   NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```
5. Deploy

### Access Dashboard

1. Open deployed URL
2. Enable courses you want to monitor
3. Toggle categories within each course
4. Changes take effect on next sync run

---

## 7️⃣ Testing

### Manual Workflow Trigger

1. Go to **Actions** tab in GitHub
2. Select "Google Classroom → Apple Reminders Sync"
3. Click **Run workflow**
4. Monitor execution logs

### Verify Results

1. Check Supabase **Table Editor**:
   - `courses` table should have your courses
   - `categories` table should have topics
   - `assignments` table should populate
2. Open Apple Reminders app on iPhone
3. Look for new lists matching course names
4. Assignments should appear with alarm notifications

---

## 8️⃣ Troubleshooting

### No Courses Appearing

- Verify Google OAuth scopes are **exactly**:
  - `classroom.courses.readonly`
  - `classroom.coursework.me` (NOT `.readonly`)
  - `classroom.student-submissions.me.readonly`
- **Do NOT** enable all 22 scopes - only use the 3 above
- Check refresh token is valid (regenerate if scopes were wrong)
- Run workflow manually and check logs

### Apple Reminders Not Syncing

- Verify app-specific password is correct
- Check iCloud is enabled on your device
- Ensure CalDAV URL is `https://caldav.icloud.com`
- Wait a few minutes for iCloud sync

### Email Alerts Not Working

- Verify Resend API key is correct
- Check alert email matches your verified domain
- If using onboarding domain, emails can only go to verified email
- Look for emails in spam folder
- Check Resend dashboard for delivery logs

### Workflow Failing

- Check GitHub Actions logs for detailed error
- Verify all secrets are set correctly
- Ensure Supabase project is active

---

## 9️⃣ Maintenance

### Monitoring

- Check email for failure alerts
- Review GitHub Actions runs weekly
- Monitor Supabase usage (free tier limits)

### Updating Configuration

- Use frontend dashboard to enable/disable courses
- No code changes needed for filtering
- Workflow runs automatically 3x daily

---

## 🔟 Security Best Practices

1. **Never commit** `.env` files or credentials
2. Use **private** GitHub repository
3. Rotate **app-specific passwords** periodically
4. Keep **Supabase** RLS policies enabled
5. Review **GitHub Actions logs** regularly

---

## ✅ Setup Complete!

Your automation is now running. Reminders will sync automatically at:
- 12:00 PM IST
- 06:00 PM IST
- 10:00 PM IST

Configure courses and categories in the dashboard to start receiving reminders.
