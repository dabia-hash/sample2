# Departments and Per-Semester Admission

**Date:** 2026-09-16
**Module:** `trn_student`
**Version:** `19.0.1.0.0` → `19.0.1.1.0`

## Problem

Courses have no grouping, so a registrar cannot ask "which courses does the
College of Computer Studies offer?". And `trn.student` holds one row per
student, carrying `course_id`, `year_level` and `school_year` directly, so
there is nowhere to record that a student was admitted to a particular
semester, and no identifier that says "this person is enrolled *this term*".

## Decisions

Four choices were made explicitly and shape everything below.

1. **Flat, not a child model.** Per-semester admission lives on `trn.student`
   itself: one row per student *per semester*. A separate `trn.admission`
   child model was considered and rejected.
2. **Three terms.** 1st Semester, 2nd Semester, Summer — a fixed `Selection`,
   not a configurable model.
3. **Term-stamped sequence.** The enrollment ID reads
   `ENR/2026-2027/1ST/00042`, with the counter restarting per school-year and
   term.
4. **Backfill on upgrade.** Existing rows become 1st-semester admissions of
   the academic year they already carry, with real sequence-drawn IDs.

### Accepted trade-off

Choice 1 means dropping `UNIQUE(id_number)`. `trn.student` stops being a
student registry and becomes an admissions ledger: there is no longer a single
row that *is* a given student, so nothing structurally prevents that student's
name or course differing between their own rows. This is understood and
accepted. Two things soften it, neither of which eliminates it:

- A composite `UNIQUE(id_number, school_year, semester)` replaces the dropped
  constraint, so a student still cannot be admitted to the same term twice.
- An onchange on `id_number` copies `name`, `course_id` and `year_level` from
  that student's most recent row, making a returning student a confirmation
  rather than a retype.

## Design

### `trn.department` (new)

Deliberately a near-copy of `trn.course`, so it reads like its neighbour.

| Field | Type | Notes |
| --- | --- | --- |
| `code` | Char | required, indexed, uppercased via `normalize_code`, unique |
| `name` | Char | required, translatable |
| `active` | Boolean | default `True` |
| `course_ids` | One2many → `trn.course` | |
| `course_count` | Integer | computed |

`display_name` renders `CCS — College of Computer Studies`. `create`/`write`
normalise the code and raise the same "code already used by X"
`ValidationError` as `Course._check_code_available`.

### `trn.course` (changed)

Gains `department_id` — Many2one, **required**, `ondelete="restrict"`,
indexed. Restrict, so deleting a department that still owns courses is refused
rather than cascading.

### `trn.student` (changed)

| Field | Type | Notes |
| --- | --- | --- |
| `semester` | Selection `1` / `2` / `S` | required, default `"1"` |
| `enrollment_number` | Char | readonly, `copy=False`, indexed, label "Enrollment ID" |

Named `enrollment_number`, not `enrollment_id`: an `_id` suffix means a
Many2one in Odoo, and the adjacent `id_number` already sets that precedent.

Constraints: `_unique_id_number` is replaced by
`UNIQUE(id_number, school_year, semester)`, plus a separate
`UNIQUE(enrollment_number)`. `_check_id_number_available` becomes
`_check_admission_available` so the registrar reads "Maria Santos is already
admitted to 1st Semester 2026-2027" instead of a Postgres violation.

`display_name` picks up the term — `2026-00431 — Maria Santos (1st Sem
2026-2027)` — because otherwise a student's rows are indistinguishable in any
Many2one dropdown.

### Enrollment ID generation

A counter that restarts per school-year-and-term cannot come from one static
`ir.sequence`. So `data/ir_sequence.xml` seeds a template, and
`_next_enrollment_number()` lazily creates a real sequence the first time a
term is used — code `trn.student.admission.2026-2027.1ST`, prefix
`ENR/2026-2027/1ST/`, padding 5 — then calls `next_by_code`. Same shape as
`trn_service_request/models/service_request.py:270`, keyed per term.

### Views, menus, security

- Departments: form, list, action, and a **Students → Configuration →
  Departments** menu at sequence 5, above Courses.
- Course form and list gain `department_id`; courses get a search view (they
  have none today) with group-by Department.
- Student form shows the read-only Enrollment ID beside the ID Number, and
  `semester` beside `school_year`. The search view gains per-semester filters,
  a group-by Semester, and a **Current Term** filter — the "who is enrolled
  this semester" view.
- `trn.department` ACLs mirror `trn.course` exactly: registrar reads, manager
  does everything, `base.group_system` everything.

### Migration

`migrations/19.0.1.1.0/pre-migrate.py` adds the columns and backfills in SQL —
`semester='1'` for every student, and a seeded `GENERAL` department for every
existing course — so the required columns are never NULL when Odoo enforces
them. `post-migrate.py` then walks the students through the ORM so their
enrollment numbers come from the real sequence.

### Demo data

Three departments (CCS, CBA, CED), the four existing courses filed under them,
and one student given a second-semester row so the repeat is visible.

## Testing

Written failing first.

- `test_department.py` — code normalisation, uniqueness, `course_count`, and
  that deleting a department with courses raises
  `psycopg2.errors.RestrictViolation`.
- `test_student.py` — the same student admitted to two different semesters
  succeeds; a duplicate `(id_number, school_year, semester)` raises; the
  enrollment number matches the term-stamped format; the counter restarts
  across terms.
- `test_security.py` — registrar reads departments, manager writes them.
- `test_demo_data.py` — the departments exist and courses carry one.
- `tests/common.py` — a `TEST-`-prefixed department fixture, per the demo-data
  collision pitfall in CLAUDE.md.
