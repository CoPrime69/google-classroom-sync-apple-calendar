# Local Testing Guide

## Prerequisites

Before testing, ensure you have:
- Python 3.11+ installed
- Node.js 18+ installed (for frontend)
- All service accounts created (Supabase, Google, Apple, Resend)

## Step 1: Backend Setup

### 1.1 Create Environment File

```bash
cd backend
cp .env.example .env
```

### 1.2 Fill in Your Credentials

Edit `backend/.env` with your actual credentials:

```env
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbG...

# Google Classroom
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_REFRESH_TOKEN=1//xxxxx

# Apple Reminders
APPLE_USERNAME=your-email@icloud.com
APPLE_PASSWORD=xxxx-xxxx-xxxx-xxxx
CALDAV_URL=https://caldav.icloud.com

# Email Alerts
RESEND_API_KEY=re_xxxxx
ALERT_EMAIL=your-email@example.com

# Timezone
TIMEZONE=Asia/Kolkata

# Notification Window
NOTIFICATION_START_HOUR=7
NOTIFICATION_END_HOUR=24
```

### 1.3 Install Dependencies

```bash
py -3.11 -m venv venv311
.\venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 1.4 Test Credentials

```bash
python test_credentials.py
```

**Expected output:**
```
✅ PASS: Configuration
✅ PASS: Supabase
✅ PASS: Google Classroom
✅ PASS: Apple Reminders
✅ PASS: Resend
```

If any test fails, fix the credentials before proceeding.

### 1.5 Run Full Sync

```bash
python main.py
```

**What to check:**
- No errors in console
- Supabase tables populated (courses, categories, assignments)
- Apple Reminders app shows new reminders
- Check your iPhone to verify sync

## Step 2: Frontend Setup

### 2.1 Create Environment File

```bash
cd ../frontend
cp .env.example .env.local
```

### 2.2 Fill in Supabase Credentials

Edit `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbG...
```

### 2.3 Install Dependencies

```bash
npm install
```

### 2.4 Run Development Server

```bash
npm run dev
```

### 2.5 Test Dashboard

Open browser: http://localhost:3000

**What to test:**
- [ ] Page loads without errors
- [ ] Courses list appears
- [ ] Can toggle course enable/disable
- [ ] Categories list appears  
- [ ] Can toggle category enable/disable
- [ ] Changes save to Supabase

## Step 3: Test Email Alerts (Optional)

To test failure emails:

1. Temporarily break a credential in `.env` (e.g., wrong Supabase URL)
2. Run `python main.py` twice (triggers failure alert after 2 failures)
3. Check your inbox for alert email
4. Fix credential and run again (triggers recovery email)

## Step 4: Verify Everything

### Backend Checklist
- [x] All credentials valid
- [x] Sync runs without errors
- [x] Supabase tables populated
- [x] Reminders appear in Apple Reminders app
- [x] iPhone syncs reminders

### Frontend Checklist  
- [x] Dashboard loads
- [x] Courses displayed
- [x] Categories displayed
- [x] Toggle switches work
- [x] Changes persist

## Common Issues

### "Module not found" error
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### "Invalid credentials" error
- Double-check `.env` file has correct values
- No extra spaces or quotes
- Verify each service credential separately

### Frontend won't start
```bash
cd frontend
rm -rf .next node_modules
npm install
npm run dev
```

### No reminders showing up
- Check Reminders app is using same iCloud account
- Verify CALDAV_URL is correct
- Check Apple app-specific password is active

## Next Steps

Once local testing passes:
1. Review [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
2. Set up GitHub secrets
3. Deploy frontend to Vercel
4. Test GitHub Actions workflow

---

**All tests passing?** → Ready to deploy! 🚀
