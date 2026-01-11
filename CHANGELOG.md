# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-11

### Added

#### Core Features
- Google Classroom API integration with OAuth
- Apple Reminders sync via CalDAV
- Supabase database for state management
- Course and category filtering
- Submission-aware notifications
- Deadline extension detection
- Multi-alarm reminders (48h, 24h, 6h, 2h)
- Time-windowed alerts (7 AM - midnight)

#### Automation
- GitHub Actions cron workflow (3x daily)
- Automatic retry on failure (10-minute delay)
- Email alerts via Resend on double failure
- Failure tracking and recovery detection

#### Frontend
- Next.js dashboard for configuration
- Course enable/disable toggle
- Category enable/disable toggle
- Responsive UI with Tailwind CSS
- Real-time Supabase integration

#### Documentation
- Comprehensive setup guide
- Architecture documentation
- API reference
- Troubleshooting guide
- FAQ
- Quick start guide
- Contributing guide

#### Developer Tools
- Credential testing script
- Environment configuration templates
- Database schema with migrations
- Type-safe TypeScript interfaces

### Technical Details

#### Backend
- Python 3.11+
- Modular architecture with separate clients
- Timezone-aware datetime handling (IST)
- Efficient state-driven processing
- Comprehensive error handling

#### Database
- PostgreSQL (Supabase)
- Normalized schema with foreign keys
- Indexes for performance
- Row-level security enabled
- Automatic timestamp tracking

#### Infrastructure
- GitHub Actions for scheduling
- Vercel for frontend hosting
- Environment variable management
- Secure credential storage

---

## [Unreleased]

### Planned Features
- [ ] Notion integration
- [ ] Google Calendar sync
- [ ] Slack notifications
- [ ] Custom alarm intervals
- [ ] Per-assignment ignore
- [ ] Dashboard analytics
- [ ] Multi-user support
- [ ] Mobile app

### Planned Improvements
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance monitoring
- [ ] Backup/restore functionality
- [ ] Advanced filtering options
- [ ] Reminder templates

---

## Version History

### 1.0.0 (2026-01-11)
Initial release with core functionality

---

## Migration Guide

No migrations needed for initial release.

---

## Breaking Changes

None for initial release.

---

## Security Updates

- OAuth with refresh tokens (no password storage)
- App-specific passwords for Apple
- GitHub Secrets for credential management
- Supabase RLS policies enabled

---

## Known Issues

None reported yet. See [GitHub Issues](../../issues) for current status.

---

## Contributors

Thank you to all contributors!

---

[1.0.0]: https://github.com/username/project_self/releases/tag/v1.0.0
