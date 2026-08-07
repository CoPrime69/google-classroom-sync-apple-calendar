# Grade Tracker — Design

**Date:** 2026-08-07
**Status:** Approved, pending implementation plan

## Problem

There is no way to know where a course stands part-way through a semester.
Marks arrive component by component, each course weights its components
differently, and most courses count only the best few quizzes or assignments.
Working that out by hand every time a mark comes back is tedious and
error-prone.

The tracker answers one question per course: **out of the weight graded so far,
how much have I earned?**

## Scope

In scope:

- Per-course component groups with weights and a count of how many contribute.
- Manual mark entry in Notion.
- A running standing per course, expressed as a fraction of the weight graded.
- Durable storage of every group, component and computed result in Supabase,
  plus an append-only history of how each course moved over the term.

Out of scope:

- Auto-creating components from Google Classroom coursework. Classroom carries
  no marks, so the link would save little typing while coupling two systems.
- Target grades and "what do I need on the final" projections.
- Any grade display in the existing Next.js dashboard. Notion is the interface.

## Architecture

Notion is the only surface the user touches. Supabase is the store of record and
holds history. A scheduled Python job moves data between them and does the
arithmetic.

```
Notion (user types)                  Supabase (truth + history)
  Setup DB      ──read──┐
  Marks DB      ──read──┤
                        ▼
                    sync.py ──upsert inputs──► grade_groups
                        │                      grade_components
                        ▼
                  calculator.py  (pure, unit-tested)
                        │
                        ├──append on change────► grade_snapshots
                        │
                        └──write display──► Notion Summary DB
```

### Field ownership

Bidirectional at the system level, single-writer at the field level. This is
what removes the usual two-way-sync conflict problem: there is never a question
of who wins, because no field has two writers.

| Field | Owner |
|---|---|
| Group name, weight, counted count | Notion (user) |
| Component name, score, max | Notion (user) |
| Computed standing, dropped flags, effective weights | Supabase (job) |
| Everything on the Summary database | Supabase (job) |

The Next.js dashboard must not gain grade editing. Doing so would give the input
fields a second writer and reintroduce exactly the conflict this partition
avoids.

### Modules

New package `backend/src/grades/`:

- **`calculator.py`** — pure functions. Takes groups and components, returns a
  standing. No network, no database. All counting and weighting logic lives
  here, which is what makes it testable.
- **`notion.py`** — thin Notion API wrapper. Reads the two input databases,
  writes display fields and Summary rows.
- **`sync.py`** — orchestration only. Wires the other two to Supabase.

Entry point `backend/grades_main.py`, mirroring `main.py`.

### Scheduling

A **separate** GitHub Actions workflow, `.github/workflows/grades.yml` — not a
step in `sync.yml`. Different concern and different failure mode: a Notion
outage must not fail the calendar sync, and a grade bug must not trigger the
sync's failure-alert email.

Requires one new secret, `NOTION_API_KEY`, in the `google-classroom-sync`
environment.

## Data model

### Supabase

```sql
grade_groups
  id              uuid primary key
  course_id       text references courses(id)
  notion_page_id  text unique          -- join key back to Notion
  name            text                 -- free text, no enum
  weight          numeric              -- percent of the course
  counted         integer null         -- how many contribute; NULL = all of them
  archived        boolean default false
  created_at, updated_at

grade_components
  id               uuid primary key
  group_id         uuid references grade_groups(id)
  notion_page_id   text unique
  name             text
  score            numeric null         -- NULL means not graded yet
  max_score        numeric
  is_dropped       boolean              -- computed
  effective_weight numeric              -- computed
  archived         boolean default false
  created_at, updated_at

grade_snapshots                          -- append-only
  id             bigserial primary key
  course_id      text references courses(id)
  captured_at    timestamptz default now()
  earned_weight  numeric
  graded_weight  numeric
  percentage     numeric
  detail         jsonb                   -- full breakdown, incl. dropped names
```

Four decisions worth stating explicitly:

**`counted` replaces an expected-count / drop-count pair.** Real policies are
written as "best N", not "drop K". CV states "5–7 Quizzes", dropping n−1 at six
and n−2 at seven — which is simply *best 5* in both cases. A drop-count model
would require editing the row every time the professor adds a quiz; `counted`
absorbs it with no edit and keeps each quiz worth a stable `weight / counted`.

**`counted` is nullable, and NULL means "all of them count".** EVS states
"Class Assignments 10% — will be assigned as needed": the total is unknown and
none are dropped. A required count would mean editing the row every time an
assignment appears. With NULL the weight splits evenly across however many
component rows exist, so adding a fourth assignment silently re-splits 10% into
2.5% each. This requires creating the row when the assignment is *set* rather
than when it is marked; otherwise a single graded row transiently appears to
carry the group's entire weight.

**`score` is nullable and NULL is not zero.** A component that exists but has
not been graded is excluded from both numerator and denominator. Treating
ungraded as zero would make the tool report a falsely low standing.

**Deletes are soft.** Removing a row in Notion sets `archived`. Durable records
were the reason for choosing Supabase as store of record; a hard delete would
defeat that.

**Snapshots append only when the computed result changes.** A repeatedly
scheduled job would otherwise produce thousands of identical rows and make the
history unreadable. `detail` is denormalised JSON so a snapshot stays truthful
even after a weight is later edited.

Group `name` carries no enum or check constraint. Courses differ freely — CV has
Assignments / Quizzes / Mini Project / Minor / Major, while IBM has
Participation / Group Project / Minor / Major with no quizzes at all. Courses
with two groups and courses with eight behave identically. Adding a group in
Notion creates it on the next run; no code change is ever needed for a new kind
of component.

### Notion

Three databases.

**Setup** — one row per group per course. User-owned. Filled in once per course
from the syllabus, since grading schemes are published upfront.

All four current-semester courses, as actually published:

| Course | Category | Weight | Counts |
|---|---|---|---|
| CSL7360 (CV) | Assignments | 10 | 2 |
| CSL7360 | Quizzes | 15 | 5 |
| CSL7360 | Mini Project | 15 | 1 |
| CSL7360 | Minor | 20 | 1 |
| CSL7360 | Major | 40 | 1 |
| MSL4010 (IBM) | Participation | 10 | 1 |
| MSL4010 | Group Project | 15 | 1 |
| MSL4010 | Minor | 25 | 1 |
| MSL4010 | Major | 50 | 1 |
| LAL7490 (Indian Econ) | Assignments | 25 | 2 |
| LAL7490 | Minor | 25 | 1 |
| LAL7490 | Major | 50 | 1 |
| CIL4010 (EVS) | Minor | 20 | 1 |
| CIL4010 | Major | 50 | 1 |
| CIL4010 | Class Assignments | 10 | *(blank)* |
| CIL4010 | PPT presentation | 10 | 1 |
| CIL4010 | Video presentation | 10 | 1 |

Every course sums to 100.

`Counts` is how many components in that category contribute. Blank means all of
them. Editable at any time.

Two things these real policies demonstrate. CV's "5–7 Quizzes" needs no edits as
the count varies, because `Counts = 5` already expresses n−1 at six and n−2 at
seven. And Indian Econ's published table lists "Quizzes" and "Projects" rows
with no weightage — unused template placeholders. Those rows are simply never
created; the three that carry weights already total 100.

**Marks** — one row per component. User-owned except the read-only columns.

| Course | Category | Name | Score | Max |
|---|---|---|---|---|
| CSL7360 | Quizzes | Quiz 1 | 8 | 10 |
| CSL7360 | Quizzes | Quiz 2 | 5 | 10 |

Job-written read-only columns: `Counted`, `Effective weight`. A per-category
rollup shows earned over available from counted components only, e.g. `32/40`.

**Summary** — one row per current-semester course. Entirely job-owned, created
and maintained by the job. Deliberately minimal: no nested tables.

| Course | Marks |
|---|---|
| CSL7360 | 15.67 / 20.0 |
| MSL4010 | 22.30 / 30.0 |

`Marks` is earned weight over weight graded so far, shown as a fraction so the
current position is legible at a glance. It is not out of 100: early in the term
"13.7/100" would look alarming and mean nothing.

### Course matching and scoping

Notion rows link to courses by `course_code` (CSL7360, MSL4010…), matched
case-insensitively. Only courses whose `semester` equals
`settings.current_semester` are processed, reusing the existing filter so past
semesters are not recomputed.

A Notion row whose course code matches no course **fails loudly** — the row is
reported in the job output and flagged in Notion. Silently skipping it would
mean a typo quietly stops a course from ever updating.

## Grade calculation

For each group:

```
components = non-archived rows in the group
graded     = those with a non-null score

keep = len(components) if counted is NULL else max(1, counted)

rank graded by score/max_score descending, ties broken by name
kept    = top min(len(graded), keep)
dropped = the remainder

weight_per_survivor = weight / keep

for each kept component c:
    earned        += (c.score / c.max_score) * weight_per_survivor
    graded_weight += weight_per_survivor
```

Course standing is `earned / graded_weight`, reported as that fraction.

Dropped components are excluded from both sides — of the weighted figures and of
the Marks-page rollup. The denominator only ever contains marks that can
actually be earned.

Three points that are deliberate:

**Divide by `keep`, not by the number graded so far.** With two of five quizzes
done and `counted = 5`, each is worth 15/5 = 3%, so 6% of the course is graded —
not 15%. Dividing by the graded count would inflate early-term components and
produce a number that silently rewrites itself later.

**Dropping starts only once there is a surplus.** While `len(graded)` is at or
below `keep`, every graded component counts, via `min(len(graded), keep)`. The
drop begins when the next one is entered. This keeps the standing honest today
and lets it improve automatically later.

**Rank by `score/max_score`, not raw score.** A 9/10 beats a 15/20. Raw
comparison drops the wrong component whenever maximums differ within a group.
Where all components in a group share a maximum, this distinction never fires.

### Worked example

CV quizzes: weight 15%, `counted = 5`. The professor holds seven; six are
graded so far. Each surviving quiz is worth 15/5 = 3%.

| Quiz | Score | score/max | Weight | Earned |
|---|---|---|---|---|
| Q3 | 17/20 | 0.85 | 3.0 | 2.55 |
| Q1 | 8/10 | 0.80 | 3.0 | 2.40 |
| Q6 | 15/20 | 0.75 | 3.0 | 2.25 |
| Q4 | 7/10 | 0.70 | 3.0 | 2.10 |
| Q2 | 5/10 | 0.50 | 3.0 | 1.50 |
| Q5 | 6/20 | 0.30 | — | dropped |

Six graded, keep 5, so the single worst is dropped. When the seventh is graded,
two are dropped — with no edit to the Setup row.

Weighted: `10.80 / 15.0`. Marks-page rollup: `52/70`.

This is the case that justifies ranking by percentage. Q5 scored 6 raw marks and
Q2 scored 5, so ranking by raw score would drop **Q2** — but Q5 is 6 out of 20
(30%) while Q2 is 5 out of 10 (50%). Q5 is the worse performance and is the one
that should go. Whenever maximums differ within a group, raw ordering drops the
wrong component.

### Edge cases

| Condition | Behaviour |
|---|---|
| `graded_weight == 0` | Report "not graded yet", never 0% |
| `max_score == 0` or NULL | Skip component, warn |
| `counted < 1` | Clamp to 1, warn |
| `counted` NULL, zero component rows | Group contributes nothing; not an error |
| `len(graded) < counted` | Nothing dropped; each still worth `weight / counted` |
| `score > max_score` | Allow (bonus marks), flag |
| `score < 0` | Reject, flag, exclude |
| Group weights for a course do not sum to 100 | Compute anyway; write `⚠ weights sum to N%` on the Summary row |
| Two groups with the same name in one course | Treat as distinct (keyed on `notion_page_id`), warn |

Weight sums are warned about rather than enforced. Refusing to compute would be
obnoxious mid-term while groups are still being added; silently normalising
would hide a genuine data-entry mistake.

## Failure handling

Processing is per-course and independent. A malformed course does not prevent
the others from updating; it gets `⚠ <reason>` written to its Summary row in
place of a number.

Notion API calls retry with exponential backoff, respecting the ~3 requests per
second limit. A total Notion outage leaves Supabase updated and Notion stale —
never half-written — and the next run reconciles.

The job writes a row to `cron_logs` mirroring the existing sync, so failures are
visible in the same place. It does not reuse the sync's failure-alert email
path; grade staleness is not urgent enough to warrant an alert.

## Testing

`calculator.py` is pure, so it carries the real test suite:

- Surplus boundary: exactly `counted` graded (nothing dropped) versus one more
  (worst dropped) versus two more (worst two dropped) — the CV 5/6/7-quiz case.
- Mixed maximums within a group, where raw and percentage ordering disagree.
- Ungraded components excluded from both numerator and denominator.
- Zero graded components → "not graded yet".
- `counted` of 1 for single-component groups (Minor, Major, Participation).
- `counted` NULL: weight re-splits as rows are added (EVS Class Assignments).
- `counted < 1` clamping.
- Tie-breaking stability across repeated runs.

`notion.py` and `sync.py` get thin integration smoke tests against a scratch
Notion database. They are wiring; the logic they wire is already covered.

## Open questions

None. All design decisions above are settled.
