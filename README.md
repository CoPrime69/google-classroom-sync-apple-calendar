# Google Classroom → Apple Reminders Automation

**Smart, Selective, Submission-Aware, Deadline-Safe, Failure-Aware Automation**

A fully automated personal system that syncs Google Classroom assignments into Apple Reminders with intelligent filtering, submission tracking, and deadline handling.

## Features

- 🎯 **Course & Category Filtering** - Control which courses and topics generate reminders
- ✅ **Submission-Aware** - Automatically cancels reminders when you submit
- 📅 **Deadline Extension Handling** - Detects and updates when deadlines change
- ⏰ **Time-Windowed Alerts** - No notifications before 7 AM or after midnight
- 🔔 **Multi-Alarm Reminders** - 48h, 24h, 6h, 2h before deadline
- 🔄 **Retry Logic** - Automatic retry with email alerts on failure
- 📱 **Native iOS Integration** - Syncs via iCloud to iPhone

## Architecture

```
GitHub Actions (cron: 12 PM, 6 PM, 10 PM IST)
        ↓
Google Classroom API
        ↓
Filtering + State Logic (Supabase)
        ↓
Apple Reminders (CalDAV)
        ↓
iCloud Sync → iPhone
```

## Project Structure

```
.
├── backend/                 # Python sync engine
│   ├── src/
│   │   ├── classroom/       # Google Classroom API
│   │   ├── reminders/       # Apple Reminders CalDAV
│   │   ├── database/        # Supabase integration
│   │   ├── sync/            # Core sync logic
│   │   └── utils/           # Helpers
│   ├── requirements.txt
│   └── main.py
├── frontend/                # Configuration dashboard
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   └── package.json
├── .github/
│   └── workflows/
│       └── sync.yml         # Cron workflow
├── supabase/
│   └── schema.sql           # Database schema
└── docs/
    ├── SETUP.md
    └── API.md
```

## 📚 Documentation

- **[Quick Start](docs/QUICKSTART.md)** - Get running in 30 minutes
- **[Setup Guide](docs/SETUP.md)** - Detailed setup instructions
- **[Architecture](docs/ARCHITECTURE.md)** - System design and technical details
- **[API Reference](docs/API.md)** - Complete API documentation
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](docs/FAQ.md)** - Frequently asked questions

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone <your-repo-url>
cd project_self

# 2. Set up Supabase (5 min)
# - Create project at supabase.com
# - Run supabase/schema.sql

# 3. Configure credentials (15 min)
cd backend
cp .env.example .env
# Fill in all credentials

# 4. Test locally (2 min)
pip install -r requirements.txt
python test_credentials.py

# 5. Deploy to GitHub (5 min)
# - Push to GitHub
# - Add secrets in Settings → Secrets
# - Run workflow in Actions tab

# 6. Configure dashboard (3 min)
# - Deploy frontend to Vercel
# - Enable courses
# - Done! 🎉
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed steps.

## ✨ Key Features

### Intelligent Filtering
- Enable/disable courses via dashboard
- Filter by category/topic
- Zero spam - only relevant reminders

### Submission Awareness
- Automatically detects when you submit
- Cancels future alarms
- No manual cleanup needed

### Deadline Handling
- Detects deadline extensions
- Updates alarms automatically
- Never recreates reminders

### Time Windows
- No notifications before 7 AM
- Respects quiet hours
- IST timezone aware

### Failure Recovery
- Automatic retry on failure
- Email alerts on critical issues
- State-driven backfill

## 🏗️ Tech Stack

**Backend**
- Python 3.11
- Google Classroom API
- CalDAV (Apple Reminders)
- Supabase (PostgreSQL)
- Resend (Email)

**Frontend**
- Next.js 14
- React
- TypeScript
- Tailwind CSS
- Vercel

**Infrastructure**
- GitHub Actions (Cron)
- Supabase (Database)
- Vercel (Hosting)

## 📱 Screenshots

### Dashboard
![Dashboard](docs/images/dashboard.png)

### iPhone Reminders
![Reminders](docs/images/reminders.png)

*Screenshots coming soon*

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT - See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Google Classroom API for course data
- Apple CalDAV for reminder sync
- Supabase for database hosting
- GitHub Actions for automation

## 📧 Support

- **Issues**: [GitHub Issues](../../issues)
- **Discussions**: [GitHub Discussions](../../discussions)
- **Email**: See failure alerts for contact info

---

Built with ❤️ for students who want zero-maintenance assignment tracking.
