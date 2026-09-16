# Subjects, Offerings, Faculty and Grades

**Date:** 2026-09-16
**Module:** `trn_student`
**Version:** `19.0.1.1.0` → `19.0.1.2.0`
**Follows:** [departments and per-semester admission](2026-09-16-departments-and-semester-admission-design.md)

## Problem

An admission records that a student is enrolled for a term, but not what they
are enrolled *in*. There is nowhere to say that Maria Santos takes IT101 this
semester, nowhere to record the mark she earns, and nowhere to say who teaches
it. The relationship is many-to-many in both directions — one student takes
many subjects, one subject is taken by many students — and it carries data of
its own, the grade.

## Decisions

Four choices were made explicitly and shape everything below.

1. **An offering is its own record.** `trn.subject` is a timeless catalogue
   entry; `trn.subject.offering` is that subject in one term with one faculty
   member. Students and grades attach to the offering, never to the subject.
2. **Faculty is a new `trn.faculty` model.** Not `hr.employee` (which would
   install the HR app) and not `res.partner` (shared with every other
   contact). The module stays on `base` + `trn_security`.
3. **Grades are the Philippine 1.00–5.00 steps**, as a `Selection` so that
   1.60 cannot be typed, plus `INC` and `DRP`. Blank means not yet graded.
4. **An admission's term and its offering's term must match**, enforced with a
   `ValidationError` naming both terms.

### Decisions made without being asked

Recorded so they are easy to reverse:

- `faculty_id` is **optional** on an offering. Requiring it would block
  creating an offering before it is staffed, which schools routinely do.
- `department_id` is **optional** on a subject, although it is required on a
  course, because general-education subjects span colleges.
- The junction model is named `trn.grade`, matching the vocabulary in use,
  even though a row with a blank grade is really an enrolment. Its docstring
  says so.
- No GWA or weighted average. It was not asked for and every school computes
  it differently.

## Design

### `trn.subject` (new)

The catalogue. Shaped like `trn.course` so it reads like its neighbours.

| Field | Type | Notes |
| --- | --- | --- |
| `code` | Char | required, indexed, uppercased via `normalize_code`, unique |
| `name` | Char | required, translatable |
| `units` | Float | required, default `3.0` |
| `department_id` | Many2one → `trn.department` | optional, `ondelete="restrict"` |
| `active` | Boolean | default `True` |
| `offering_ids` | One2many → `trn.subject.offering` | |
| `offering_count` | Integer | computed |

`display_name` renders `IT101 — Programming 1`.

### `trn.faculty` (new)

| Field | Type | Notes |
| --- | --- | --- |
| `code` | Char | required, indexed, uppercased, unique, e.g. `REYES-J` |
| `name` | Char | required |
| `department_id` | Many2one → `trn.department` | optional, `ondelete="restrict"` |
| `active` | Boolean | default `True` |
| `offering_ids` | One2many → `trn.subject.offering` | |
| `offering_count` | Integer | computed |

`display_name` renders `REYES-J — Prof. Juan Reyes`.

### `trn.subject.offering` (new)

One subject, one term, one professor.

| Field | Type | Notes |
| --- | --- | --- |
| `subject_id` | Many2one → `trn.subject` | required, `ondelete="restrict"` |
| `school_year` | Char | required, `YYYY-YYYY`, same validation as an admission |
| `semester` | Selection | required, `1` / `2` / `S` |
| `faculty_id` | Many2one → `trn.faculty` | optional, `ondelete="restrict"` |
| `grade_ids` | One2many → `trn.grade` | |
| `student_count` | Integer | computed |

Constrained `UNIQUE(subject_id, school_year, semester)` — one offering per
subject per term, since sections were not wanted. `display_name` renders
`IT101 — Programming 1 (1st Sem 2026-2027)`.

### `trn.grade` (new)

The junction, and the reason the relationship is many-to-many in both
directions: an admission has many grade rows, an offering has many grade rows.

| Field | Type | Notes |
| --- | --- | --- |
| `student_id` | Many2one → `trn.student` | required, `ondelete="cascade"` |
| `offering_id` | Many2one → `trn.subject.offering` | required, `ondelete="restrict"` |
| `grade` | Selection | optional — blank means not yet graded |
| `subject_id` | related `offering_id.subject_id` | stored, for grouping |
| `faculty_id` | related `offering_id.faculty_id` | stored, for grouping |
| `units` | related `subject_id.units` | stored |
| `is_passing` | Boolean | computed; `1.00`–`3.00` passes |

Grade values: `1.00 1.25 1.50 1.75 2.00 2.25 2.50 2.75 3.00 5.00 INC DRP`.

Constrained `UNIQUE(student_id, offering_id)` — one subject cannot be added
twice to one admission.

`student_id` cascades because a grade row has no meaning without its
admission; `offering_id` restricts because deleting an offering that has a
class list should be refused.

### The term rule

`_check_term_matches` runs **before** the insert, the same placement and for
the same reason as `_check_admission_available` in the previous version:
`@api.constrains` runs after the SQL constraint, so the user would get a
Postgres error instead of a sentence. The message names both terms:

> IT102 is offered in 2nd Semester 2026-2027, but this admission is for 1st
> Semester 2026-2027.

The one2many on the student form also carries a `domain` restricting the
picker to the admission's own term, so the wrong offering is both hard to pick
and impossible to save.

### Shared term code

`SCHOOL_YEAR_PATTERN`, the `YYYY-YYYY` validation and `SEMESTER_SELECTION`
currently live on `trn.student`. Three models now need them, so they move to
`models/academic_term.py` and all three import from there. This is a targeted
tidy-up of code the change already touches, not a refactor of anything else.

### Screens

- **Student form** — directly below the existing details group, in a titled
  section rather than a notebook tab: an editable list of `grade_ids` showing
  Subject, Faculty, Units and Grade, with the picker filtered to the
  admission's term.
- **Subject Offering form** — subject, term and professor in the header, then
  the class list: an editable list of `grade_ids` showing Enrollment ID,
  Student, Course and Grade, so grades can be keyed down the column.
- **Menus** — `Students → Subject Offerings` (operational, beside All
  Students); `Configuration → Subjects` and `Configuration → Faculty`
  (catalogue, beside Departments and Courses).

### Security

Mirrors the split already in place:

| Model | Registrar | Manager |
| --- | --- | --- |
| `trn.subject` | read | all |
| `trn.faculty` | read | all |
| `trn.subject.offering` | read | all |
| `trn.grade` | read, write, create | all |

Enrolling a student in subjects and recording marks is the registrar's day
job; maintaining the catalogue and deciding what is offered is not.

### Demo data

Three faculty, five subjects, offerings across both semesters of 2026-2027,
and grades for the existing demo students — including one blank and one `INC`,
so the not-yet-graded and incomplete states are visible on screen.

## Testing

Written failing first.

- `test_subject.py` / `test_faculty.py` — code normalisation, uniqueness,
  blank rejection, `display_name`, `offering_count`, restrict-on-delete.
- `test_subject_offering.py` — one offering per subject per term, academic
  year validation, `student_count`, and that an offering with a class list
  cannot be deleted.
- `test_grade.py` — the term-match rejection in both directions, the
  many-to-many in both directions, a blank grade being a valid ungraded row,
  `is_passing` at the 3.00/5.00 boundary, `UNIQUE(student_id, offering_id)`,
  and that deleting an admission takes its grade rows with it.
- `test_security.py` — registrar records grades but cannot maintain the
  catalogue.
- `test_demo_data.py` — offerings carry a term, and the demo shows both a
  graded and an ungraded row.
- `tests/common.py` — `TEST-` prefixed subject, faculty and offering
  fixtures, per the demo-data collision pitfall in CLAUDE.md.

No migration: every table here is new. The version bump to `19.0.1.2.0` is
what triggers the upgrade.
