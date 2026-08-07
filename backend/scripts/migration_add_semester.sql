-- Migration: per-course semester + a single global "current semester" setting.
--
-- The sync previously processed every course with enabled = true. Because
-- courses accumulate across semesters (Classroom keeps returning old ones, and
-- whether a course is ARCHIVED depends on the teacher, not the student), that
-- meant last semester's courses kept syncing. Courses are now additionally
-- filtered to the semester named in settings.current_semester.
--
-- Safe to re-run: every statement is guarded.

-- 1. Per-course semester label, e.g. '7th sem'. Hand-entered from the dashboard.
ALTER TABLE courses ADD COLUMN IF NOT EXISTS semester text;

CREATE INDEX IF NOT EXISTS courses_semester_enabled_idx
    ON courses (semester, enabled);

-- 2. Single-row settings table holding the semester currently being synced.
--    The CHECK constraint keeps it a singleton so there is no ambiguity about
--    which row the sync should read.
CREATE TABLE IF NOT EXISTS settings (
    id               integer     PRIMARY KEY DEFAULT 1,
    current_semester text,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT settings_singleton CHECK (id = 1)
);

INSERT INTO settings (id, current_semester)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

-- 3. The dashboard talks to Supabase with the anon key, so it needs explicit
--    access to the new table. Mirrors how the existing tables are exposed.
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS settings_anon_read  ON settings;
DROP POLICY IF EXISTS settings_anon_write ON settings;

CREATE POLICY settings_anon_read  ON settings FOR SELECT USING (true);
CREATE POLICY settings_anon_write ON settings FOR UPDATE USING (true) WITH CHECK (true);
