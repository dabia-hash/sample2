# Student Information System — Design

**Date:** 2026-09-15
**Module:** `trn_student`
**Layer:** 2 (Domain Core)
**Status:** Approved

## Purpose

Hold the registrar's core student record: a unique ID number, the student's
name, the course they are enrolled in, and their year. Nothing else. Grades,
attendance, and billing are separate concerns and are explicitly out of scope.

## Scope

In scope:

- A student record keyed by a manually entered, unique ID number.
- A course master list, so a course is one record rather than a spelling.
- Year captured in two parts: year level and academic year.
- Registrar and manager roles, list/form/search views, menus, demo data, tests.

Out of scope (each is a separate feature):

- Chatter (`mail.thread`), activities, and notifications.
- Any link to `res.partner` or `res.users`.
- Enrollment history across academic years.
- Grades, subjects, sections, attendance, tuition, photos.

## Models

### `trn.course`

A course offered by the institution.

| Field           | Type                | Rules                                       |
| --------------- | ------------------- | ------------------------------------------- |
| `code`          | Char                | required, unique (SQL), stripped + uppercase |
| `name`          | Char                | required                                    |
| `active`        | Boolean             | default `True`; archive rather than delete  |
| `student_ids`   | One2many            | inverse of `trn.student.course_id`          |
| `student_count` | Integer, computed   | non-stored, counts `student_ids`            |

`_order = "code"`. Display name is `CODE — Name`, e.g.
`BSIT — BS Information Technology`. `_rec_names_search` covers both `code` and
`name` so typing either finds the course.

### `trn.student`

A student enrolled in a course.

| Field         | Type                     | Rules                                          |
| ------------- | ------------------------ | ---------------------------------------------- |
| `id_number`   | Char                     | required, indexed, unique (SQL), `copy=False`   |
| `name`        | Char                     | required; the student's full name               |
| `course_id`   | Many2one `trn.course`    | required, `ondelete="restrict"`                 |
| `year_level`  | Selection                | required; `1`–`4` → 1st–4th Year                |
| `school_year` | Char                     | required; `YYYY-YYYY`                           |
| `active`      | Boolean                  | default `True`; archive rather than delete      |

`_order = "id_number"`. Display name is `ID — Name`, e.g.
`2026-00431 — Maria Santos`. `_rec_names_search` covers `id_number` and `name`.

`ondelete="restrict"` on `course_id` is deliberate: deleting a course that still
has students would silently orphan them, so the database refuses. Archive the
course instead.

## Validation

**ID number uniqueness.** A SQL unique constraint on `id_number` is the
authority. Before it fires, `create` and `write` normalize the value — strip
surrounding whitespace, collapse internal runs of whitespace, uppercase — so
`" 2026-00431 "` and `"2026-00431"` cannot both exist. A duplicate raises a
`ValidationError` naming the student that already holds the number, rather than
surfacing a raw Postgres error.

An `id_number` that is empty or whitespace-only is rejected with a
`ValidationError`; `required=True` alone does not catch `"   "`.

**Course code uniqueness.** Same treatment as `id_number`: normalized on write,
SQL unique constraint, readable error.

**School year.** Must match `^\d{4}-\d{4}$` *and* the second year must be
exactly one greater than the first. So `2026-2027` is valid; `2026-2030`,
`2026-2025`, `2026/2027`, and `26-27` are all rejected with a `ValidationError`
that states the expected format.

## Views

- **List** — ID number, name, course, year level, school year.
- **Form** — ID number and name in the title area; course, year level, and
  school year in a single group below.
- **Search** — text search across ID number, name, and course; filters per year
  level; group-by on course, year level, and school year; an Archived filter.

Menus: a **Students** root menu containing **Students**, and a
**Configuration** submenu containing **Courses**.

## Security

Two groups, following the pattern already used by `trn_service_request`:

| Group                         | Students             | Courses              |
| ----------------------------- | -------------------- | -------------------- |
| **Student: Registrar**        | read, write, create  | read                 |
| **Student: Registrar Manager** | + delete            | read, write, create, delete |

Registrar Manager implies Registrar. `base.group_system` holds full access on
both models. All of this lives in `security/ir.model.access.csv` and
`security/security_groups.xml`.

There are no record rules: every registrar sees every student. Restricting
students by course or campus is a later feature and would need a real
requirement behind it.

## Testing

Tests are written before the implementation, per the project's TDD rule, and run
as the relevant user rather than admin.

`tests/test_student.py`

- A duplicate `id_number` is rejected.
- `id_number` differing only by whitespace or case is treated as a duplicate.
- A whitespace-only `id_number` is rejected.
- `school_year` accepts `2026-2027` and rejects `2026-2030`, `2026-2025`,
  `2026/2027`, `26-27`.
- `course_id`, `year_level`, and `name` are required.
- `display_name` renders `ID — Name`.
- Searching by ID number or by name finds the student.

`tests/test_course.py`

- A duplicate `code` is rejected, including by case.
- `student_count` reflects the linked students.
- Deleting a course that still has students is refused.
- `display_name` renders `CODE — Name`.

`tests/test_security.py`

- A registrar can read, create, and write students, but not delete them.
- A registrar can read courses but not create them.
- A manager can delete students and manage courses.

`tests/test_demo_data.py`

- Demo courses and students load, and every demo student has a course, a year
  level, and a valid school year.

## Demo data

Four courses (BSIT, BSCS, BSBA, BSED) and six students spread across them and
across year levels, created with `tracking_disable=True`.

## File layout

```
trn_student/
  __init__.py
  __manifest__.py
  models/__init__.py
  models/course.py
  models/student.py
  security/security_groups.xml
  security/ir.model.access.csv
  views/course_views.xml
  views/student_views.xml
  views/menus.xml
  demo/student_demo.xml
  readme/DESCRIPTION.md
  tests/__init__.py
  tests/common.py
  tests/test_student.py
  tests/test_course.py
  tests/test_security.py
  tests/test_demo_data.py
```

Manifest: `depends = ["base"]`, `application = True`, `auto_install = False`,
`license = "LGPL-3"`, `version = "19.0.1.0.0"`, `category = "trn/Education"`.

`application = True` because Students is a top-level menu a registrar opens
directly, not a background extension of another module.

## Verification

1. `./odoo-project test trn_student`
2. `pre-commit run --files <changed files>`
3. `/verify-tests`
4. Install the module on the running instance and confirm the Students menu,
   the list, and a duplicate-ID error message in the UI.
