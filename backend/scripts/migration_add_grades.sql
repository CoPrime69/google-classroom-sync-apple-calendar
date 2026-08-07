-- Migration: grade tracking (groups, components, snapshot history).
--
-- Notion is where marks are typed; these tables are the store of record and
-- hold the history. Field ownership is split so nothing has two writers:
-- Notion owns weight / counted / score / max, the sync job owns is_dropped,
-- effective_weight and everything in grade_snapshots.
--
-- Safe to re-run: every statement is guarded.

-- ---------------------------------------------------------------- groups

CREATE TABLE IF NOT EXISTS grade_groups (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- course_code is the real key and is always present. course_id is a
    -- convenience link to the Classroom-synced course and is intentionally
    -- nullable: not every course is posted to Google Classroom, and grades
    -- are hand-entered regardless, so a missing Classroom record must not
    -- make a course untrackable.
    course_code    text        NOT NULL,
    course_id      text        REFERENCES courses(id) ON DELETE SET NULL,

    -- Carried on the row rather than read from courses(), because a course
    -- with no Classroom record has nowhere else to store its semester.
    semester       text        NOT NULL,

    notion_page_id text        NOT NULL UNIQUE,
    name           text        NOT NULL,
    weight         numeric     NOT NULL,

    -- How many components contribute. NULL means all of them, which is how a
    -- category with an open-ended count and no drops is expressed.
    counted        integer,

    archived       boolean     NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS grade_groups_course_semester_idx
    ON grade_groups (course_code, semester) WHERE archived = false;

-- ------------------------------------------------------------ components

CREATE TABLE IF NOT EXISTS grade_components (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id         uuid        NOT NULL REFERENCES grade_groups(id) ON DELETE CASCADE,
    notion_page_id   text        NOT NULL UNIQUE,
    name             text        NOT NULL,

    -- NULL score means "not marked yet" and is NOT zero. An ungraded
    -- component is excluded from numerator and denominator alike.
    score            numeric,
    max_score        numeric,

    -- Written by the job, never by hand.
    is_dropped       boolean     NOT NULL DEFAULT false,
    effective_weight numeric,

    archived         boolean     NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS grade_components_group_idx
    ON grade_components (group_id) WHERE archived = false;

-- -------------------------------------------------------------- snapshots

-- Append-only. A row is written only when the computed result actually
-- changes, so a repeatedly scheduled job does not bury the history in
-- thousands of identical rows.
CREATE TABLE IF NOT EXISTS grade_snapshots (
    id            bigserial   PRIMARY KEY,
    course_code   text        NOT NULL,
    course_id     text        REFERENCES courses(id) ON DELETE SET NULL,
    semester      text        NOT NULL,
    captured_at   timestamptz NOT NULL DEFAULT now(),
    earned_weight numeric     NOT NULL,
    graded_weight numeric     NOT NULL,
    percentage    numeric,

    -- Denormalised breakdown, including which components were dropped, so a
    -- snapshot stays truthful even after a weight is later edited.
    detail        jsonb       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS grade_snapshots_course_time_idx
    ON grade_snapshots (course_code, captured_at DESC);

-- ------------------------------------------------------------------ access

-- The backend and the dashboard both connect with the anon key, so access is
-- granted explicitly. Snapshots deliberately allow INSERT but not UPDATE or
-- DELETE, which is what makes the history append-only in practice and not
-- merely by convention.

ALTER TABLE grade_groups     ENABLE ROW LEVEL SECURITY;
ALTER TABLE grade_components ENABLE ROW LEVEL SECURITY;
ALTER TABLE grade_snapshots  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS grade_groups_read      ON grade_groups;
DROP POLICY IF EXISTS grade_groups_insert    ON grade_groups;
DROP POLICY IF EXISTS grade_groups_update    ON grade_groups;
CREATE POLICY grade_groups_read   ON grade_groups FOR SELECT USING (true);
CREATE POLICY grade_groups_insert ON grade_groups FOR INSERT WITH CHECK (true);
CREATE POLICY grade_groups_update ON grade_groups FOR UPDATE USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS grade_components_read   ON grade_components;
DROP POLICY IF EXISTS grade_components_insert ON grade_components;
DROP POLICY IF EXISTS grade_components_update ON grade_components;
CREATE POLICY grade_components_read   ON grade_components FOR SELECT USING (true);
CREATE POLICY grade_components_insert ON grade_components FOR INSERT WITH CHECK (true);
CREATE POLICY grade_components_update ON grade_components FOR UPDATE USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS grade_snapshots_read   ON grade_snapshots;
DROP POLICY IF EXISTS grade_snapshots_insert ON grade_snapshots;
CREATE POLICY grade_snapshots_read   ON grade_snapshots FOR SELECT USING (true);
CREATE POLICY grade_snapshots_insert ON grade_snapshots FOR INSERT WITH CHECK (true);
