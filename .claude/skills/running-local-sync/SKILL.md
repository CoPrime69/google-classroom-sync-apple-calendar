---
name: running-local-sync
description: Use when running, testing, or debugging the Classroom to Apple Calendar sync backend locally on Windows - invoking main.py, reproducing a scheduled GitHub Actions run, or investigating a local run that crashed instantly, hung for ten minutes, or reported success while doing nothing.
---

# Running the sync locally

The backend is a one-shot CLI: `backend/main.py` performs a full sync and exits.
There is no server and no watch mode. Three environment details will break a
naive `python main.py` on Windows; all three are handled by the command below.

**This is not a dry run.** Every invocation writes to the live Supabase tables
and creates, updates, or deletes real events in the configured iCloud calendars.
There is no `--dry-run` flag. Confirm with the user before running it.

## The command

```powershell
cd backend
$env:PYTHONIOENCODING = "utf-8"
.\venv311\Scripts\python.exe -u main.py
```

Bash equivalent:

```bash
cd backend && PYTHONIOENCODING=utf-8 ./venv311/Scripts/python.exe -u main.py
```

Takes roughly 30-60 seconds against ~8 courses.

## Why each part is required

| Part | Reason |
|---|---|
| `cd backend` | `src/config.py:11` calls bare `load_dotenv()`, which resolves `.env` upward from the **current working directory**. From the repo root, every credential silently reads as `None`. |
| `PYTHONIOENCODING=utf-8` | `main.py:31` prints an emoji. Windows consoles default stdout to cp1252, which raises `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f680'`. |
| `.\venv311\Scripts\python.exe` | Dependencies are pinned in `backend/venv311`, which is gitignored (`backend/.gitignore:25`). System Python has none of them. On a fresh clone: `py -3.11 -m venv venv311; .\venv311\Scripts\python.exe -m pip install -r requirements.txt`. |
| `-u` | Unbuffered, so progress is visible while it runs rather than arriving in one block at exit. |

## Do not pipe the output

Piping through `tee` or any other command replaces Python's exit code with the
pipe's, so a crashed run reports success. Redirect instead, and read `$?`
separately:

```bash
... main.py > run.log 2>&1; echo "EXIT=$?"
```

## Budget ten minutes, or background it

`main.py:101` sleeps a hard-coded 600 seconds and retries once when the first
attempt fails. A failing run therefore appears to hang for ten minutes rather
than exiting. Run it in the background, or be ready to wait.

## What success looks like

```
SYNC SUMMARY
============================================================
Assignments processed: 8
Reminders created:     0
Reminders updated:     0
Reminders cancelled:   7
============================================================

✅ Sync completed successfully
```

`Assignments processed: 0` with a `Sync completed successfully` means no course
is enabled, not that the sync worked. Course enablement lives in the Supabase
`courses` table, toggled from the frontend dashboard.

### Expected noise, not a failure

Every course logs a 403 on topics:

```
Error fetching topics for course ...: ACCESS_TOKEN_SCOPE_INSUFFICIENT
```

`GOOGLE_REFRESH_TOKEN` carries no topics scope (`docs/SETUP.md:82-86` omits it).
The code catches this and continues. Fixing it means adding
`classroom.topics.readonly` and re-minting the refresh token - do not "fix" it
mid-debugging, it is not the cause of anything.

## Verifying afterwards

`main.py:29` opens a `cron_logs` row before syncing and `main.py:39` closes it:

```bash
cd backend && PYTHONIOENCODING=utf-8 ./venv311/Scripts/python.exe -c "
from src.database import Database
r = Database().client.table('cron_logs').select('*').order('id', desc=True).limit(3).execute()
for row in r.data: print(row['id'], row['status'], row['assignments_processed'])
"
```

A row stuck at `RUNNING` is the fingerprint of a crash between those two lines -
most often the cp1252 crash above, which also takes out the `except` handler at
`main.py:58` before it can record the failure. Such rows are never cleaned up
automatically.

## Common mistakes

| Symptom | Cause |
|---|---|
| `UnicodeEncodeError: 'charmap' codec` | `PYTHONIOENCODING` not set. |
| Config validation fails though `.env` is correct | Ran from repo root, not `backend/`. |
| `ModuleNotFoundError` | Used system Python instead of `venv311`. |
| Appears to hang ~10 min | First attempt failed; `main.py:101` retry sleep. |
| Exit code 0 on an obvious crash | Output was piped; `tee`'s status won. |
| `cron_logs` row stuck at `RUNNING` | Crash between `main.py:29` and `main.py:39`. |

## Related scripts

`backend/scripts/` holds `verify_config.py` (read-only, prints course and
calendar mapping) plus `delete_assignments.py` and `cleanup_calendar.py`, which
are destructive resets. Run all three from `backend/` with the same env setup.
