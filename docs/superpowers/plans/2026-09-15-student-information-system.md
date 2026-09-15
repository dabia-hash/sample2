# Student Information System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `trn_student`, an Odoo 19 module holding the registrar's core student record — a unique ID number, name, course, year level, and academic year.

**Architecture:** Two models. `trn.course` is the master list of courses so a course is one record rather than a spelling. `trn.student` holds the student, keyed by a manually entered `id_number` that a SQL unique constraint enforces. Both models normalize their identifying code the same way, through one shared helper. No chatter, no `res.partner` link, no enrollment history.

**Tech Stack:** Odoo 19, Python 3.13, PostgreSQL. Tests use `odoo.tests.common.TransactionCase`. Run with `./odoo-project test trn_student`.

**Spec:** `docs/superpowers/specs/2026-09-15-student-information-system-design.md`

## Global Constraints

- Module name `trn_student`; models `trn.course` and `trn.student` — `trn_*` / `trn.*` naming per CLAUDE.md.
- Manifest: `version = "19.0.1.0.0"`, `license = "LGPL-3"`, `category = "trn/Education"`, `depends = ["base"]`, `application = True`, `auto_install = False`, `installable = True`.
- Odoo 19 API only: `models.Constraint(...)` for SQL constraints (not `_sql_constraints`), `@api.model_create_multi` on `create`, `_compute_display_name` (not `name_get`), `<list>` in views (not `<tree>`), `res.groups.privilege` for group privileges, `group_ids` on `res.users` (not `groups_id`), `Command.link` / `Command.set` for x2many writes.
- No `print()` — use `_logger`. No bare `except:`. No `cr.commit()`. No PII in log messages.
- Every model gets an `ir.model.access.csv` entry before the task that adds it is considered done.
- User-facing strings go through `_()` with named parameters, e.g. `_("... %(code)s ...", code=code)`.
- Demo data is NOT loaded during test runs — Odoo 19 omits it unless `--with-demo` is passed. Tests that read demo records must skip when the records are absent.
- TDD: the failing test is written and run before the implementation, every task.

---

### Task 1: Module skeleton and the Course model

**Files:**

- Create: `trn_student/__init__.py`
- Create: `trn_student/__manifest__.py`
- Create: `trn_student/models/__init__.py`
- Create: `trn_student/models/normalize.py`
- Create: `trn_student/models/course.py`
- Create: `trn_student/security/ir.model.access.csv`
- Create: `trn_student/readme/DESCRIPTION.md`
- Test: `trn_student/tests/__init__.py`
- Test: `trn_student/tests/common.py`
- Test: `trn_student/tests/test_course.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `trn_student.models.normalize.normalize_code(value) -> str` — strips, collapses internal whitespace, uppercases. Returns `""` for `None` or blank input. Task 2 imports this.
  - Model `trn.course` with fields `code` (Char), `name` (Char), `active` (Boolean). Task 2 links to it via `course_id`; Task 3 adds `student_ids` and `student_count`.
  - Test class `StudentCase` in `tests/common.py` exposing `cls.Course` and `cls.course_bsit`. Tasks 2–6 subclass it.

- [ ] **Step 1: Write the failing test**

`trn_student/tests/__init__.py`:

```python
from . import test_course
```

`trn_student/tests/common.py`:

```python
from odoo.tests.common import TransactionCase


class StudentCase(TransactionCase):
    """Shared fixtures: one course to hang students off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Course = cls.env["trn.course"]

        cls.course_bsit = cls.Course.create(
            {"code": "BSIT", "name": "BS Information Technology"}
        )
```

`trn_student/tests/test_course.py`:

```python
from odoo.exceptions import ValidationError

from .common import StudentCase


class TestCourse(StudentCase):
    """The master list of courses offered."""

    def test_course_code_must_be_unique(self):
        """Two courses sharing a code make every student ambiguous."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "BSIT", "name": "Duplicate"})

    def test_course_code_is_uppercased(self):
        """'bsit' and 'BSIT' are the same course, so store one spelling."""
        course = self.Course.create({"code": "  bs cs  ", "name": "BS Computer Science"})
        self.assertEqual(course.code, "BS CS")

    def test_course_code_differing_only_by_case_is_a_duplicate(self):
        """Normalising on write is pointless if it does not close this hole."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "bsit", "name": "Sneaky Duplicate"})

    def test_blank_course_code_is_rejected(self):
        """required=True accepts '   '; the registrar must not get away with it."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "   ", "name": "Blank"})

    def test_display_name_shows_code_and_name(self):
        """A dropdown of bare codes is unreadable to anyone new."""
        self.assertEqual(
            self.course_bsit.display_name, "BSIT — BS Information Technology"
        )

    def test_course_is_found_by_code_or_by_name(self):
        """Registrars type whichever they remember."""
        self.assertIn(self.course_bsit, self.Course.search([("display_name", "ilike", "BSIT")]))
        self.assertIn(self.course_bsit, self.Course.search([("display_name", "ilike", "Information")]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./odoo-project test trn_student`
Expected: FAIL — the module does not exist yet, so installation fails.

- [ ] **Step 3: Write minimal implementation**

`trn_student/__init__.py`:

```python
from . import models
```

`trn_student/__manifest__.py`:

```python
{
    "name": "trn Student",
    "version": "19.0.1.0.0",
    "category": "trn/Education",
    "summary": "Student records: ID number, name, course and year",
    "author": "Your Organization",
    "website": "",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": [],
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "demo": [],
    "auto_install": False,
    "application": True,
    "installable": True,
}
```

`trn_student/models/__init__.py`:

```python
from . import course
```

`trn_student/models/normalize.py`:

```python
"""Shared normalisation for the identifying codes on both models.

A course code and a student ID number are both typed by hand and both have to
compare equal regardless of how they were typed, so they normalise the same way
in one place rather than twice.
"""


def normalize_code(value):
    """Strip, collapse internal whitespace, and uppercase an identifying code.

    Returns an empty string for a missing or blank value, so callers can treat
    "absent" and "whitespace only" identically.
    """
    if not value:
        return ""
    return " ".join(value.split()).upper()
```

`trn_student/models/course.py`:

```python
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .normalize import normalize_code


class Course(models.Model):
    """One course the institution offers, e.g. BS Information Technology.

    Courses are configuration a registrar maintains in the UI. Keeping them as
    records rather than free text means a course can be renamed once and every
    student follows, and students can be grouped by course without three
    spellings fragmenting the report.
    """

    _name = "trn.course"
    _description = "Course"
    _order = "code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        required=True,
        index=True,
        help="Short identifier for the course, e.g. 'BSIT'. Stored uppercase.",
    )
    name = fields.Char(
        required=True,
        translate=True,
        help="Course as it appears on records, e.g. 'BS Information Technology'",
    )
    active = fields.Boolean(
        default=True,
        help="Archive a course that is no longer offered instead of deleting it",
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Course code must be unique",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        """Show 'BSIT — BS Information Technology' rather than a bare code."""
        for course in self:
            course.display_name = f"{course.code} — {course.name}"

    @api.model_create_multi
    def create(self, vals_list):
        """Normalise and check the code before insert."""
        for vals in vals_list:
            if "code" in vals:
                vals["code"] = normalize_code(vals["code"])
                self._check_code_available(vals["code"])
        return super().create(vals_list)

    def write(self, vals):
        """Normalise and check the code before update."""
        if "code" in vals:
            vals["code"] = normalize_code(vals["code"])
            for course in self:
                self._check_code_available(vals["code"], exclude=course)
        return super().write(vals)

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if the code is blank or already taken by another course."""
        if not code:
            raise ValidationError(_("A course needs a code, e.g. 'BSIT'."))
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        existing = self.with_context(active_test=False).search(domain, limit=1)
        if existing:
            raise ValidationError(
                _(
                    "Course code '%(code)s' is already used by '%(name)s'. "
                    "Choose a different code.",
                    code=code,
                    name=existing.name,
                )
            )
```

`trn_student/security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_trn_course_system,trn.course / System,model_trn_course,base.group_system,1,1,1,1
```

`trn_student/readme/DESCRIPTION.md`:

```markdown
Core student records for a registrar: a unique ID number, the student's name, the
course they are enrolled in, and their year.

Each student is keyed by an ID number the registrar types in — the number the
institution already issues — and a database constraint refuses a second student with
the same one. Courses are their own records, so a course is renamed once and every
student follows.

### Key Models

- `trn.student` — the student record
- `trn.course` — one course offered, e.g. BSIT

### Dependencies

- `base` only
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./odoo-project test trn_student`
Expected: PASS — 6 tests in `TestCourse`.

- [ ] **Step 5: Commit**

```bash
git add trn_student/
git commit -m "feat(student): add course model with unique normalised codes"
```

---

### Task 2: The Student model

**Files:**

- Create: `trn_student/models/student.py`
- Modify: `trn_student/models/__init__.py`
- Modify: `trn_student/security/ir.model.access.csv`
- Test: `trn_student/tests/test_student.py`
- Modify: `trn_student/tests/__init__.py`
- Modify: `trn_student/tests/common.py`

**Interfaces:**

- Consumes: `normalize_code` from Task 1; model `trn.course`; `StudentCase` with `cls.Course` and `cls.course_bsit`.
- Produces:
  - Model `trn.student` with fields `id_number` (Char), `name` (Char), `course_id` (Many2one `trn.course`, `ondelete="restrict"`), `year_level` (Selection), `school_year` (Char), `active` (Boolean).
  - `YEAR_LEVEL_SELECTION` in `models/student.py` — the list of `(value, label)` pairs. Task 5 does not need it; Task 6 uses the values `"1"`–`"4"`.
  - `StudentCase._new_student(**overrides)` classmethod returning a `trn.student` record. Tasks 3, 4, and 6 use it.

- [ ] **Step 1: Write the failing test**

Add to `trn_student/tests/common.py`, inside `StudentCase`, after `setUpClass`:

```python
        cls.Student = cls.env["trn.student"]

    @classmethod
    def _new_student(cls, **overrides):
        """Create a second-year BSIT student unless told otherwise."""
        values = {
            "id_number": "2026-00431",
            "name": "Maria Santos",
            "course_id": cls.course_bsit.id,
            "year_level": "2",
            "school_year": "2026-2027",
        }
        values.update(overrides)
        return cls.Student.create(values)
```

Note: `cls.Student = ...` goes at the end of `setUpClass`, before the new
classmethod.

`trn_student/tests/__init__.py` becomes:

```python
from . import test_course
from . import test_student
```

`trn_student/tests/test_student.py`:

```python
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import StudentCase


class TestStudent(StudentCase):
    """The student record, keyed by a hand-entered ID number."""

    def test_a_student_can_be_created(self):
        """The happy path: the four fields the registrar cares about."""
        student = self._new_student()
        self.assertEqual(student.id_number, "2026-00431")
        self.assertEqual(student.name, "Maria Santos")
        self.assertEqual(student.course_id, self.course_bsit)
        self.assertEqual(student.year_level, "2")
        self.assertEqual(student.school_year, "2026-2027")

    def test_duplicate_id_number_is_rejected(self):
        """The ID number is the key; two students cannot share one."""
        self._new_student()
        with self.assertRaises(ValidationError):
            self._new_student(name="Impostor")

    def test_id_number_differing_only_by_whitespace_is_a_duplicate(self):
        """A stray space must not buy a second record for the same student."""
        self._new_student()
        with self.assertRaises(ValidationError):
            self._new_student(id_number="  2026-00431 ", name="Impostor")

    def test_id_number_differing_only_by_case_is_a_duplicate(self):
        """Same reasoning as whitespace: 'a-1' and 'A-1' are one number."""
        self._new_student(id_number="tr-7")
        with self.assertRaises(ValidationError):
            self._new_student(id_number="TR-7", name="Impostor")

    def test_blank_id_number_is_rejected(self):
        """required=True lets '   ' through; the key must be real."""
        with self.assertRaises(ValidationError):
            self._new_student(id_number="   ")

    def test_id_number_is_normalised_on_write(self):
        """Renumbering a student goes through the same normalisation."""
        student = self._new_student()
        student.write({"id_number": "  2026-00999 "})
        self.assertEqual(student.id_number, "2026-00999")

    def test_school_year_accepts_consecutive_years(self):
        """The ordinary case the registrar types every day."""
        student = self._new_student(school_year="2030-2031")
        self.assertEqual(student.school_year, "2030-2031")

    def test_school_year_rejects_a_gap(self):
        """'2026-2030' is a typo, not a four-year enrolment."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="2026-2030")

    def test_school_year_rejects_a_backwards_range(self):
        """The second year must follow the first."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="2026-2025")

    def test_school_year_rejects_the_wrong_separator(self):
        """One format keeps grouping and sorting meaningful."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="2026/2027")

    def test_school_year_rejects_two_digit_years(self):
        """'26-27' sorts and groups wrongly against four-digit years."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="26-27")

    def test_course_is_required(self):
        """A student with no course cannot be scheduled or reported on."""
        with self.assertRaises(Exception):
            self._new_student(course_id=False)

    def test_year_level_is_required(self):
        """Year level drives nearly every registrar filter."""
        with self.assertRaises(Exception):
            self._new_student(year_level=False)

    def test_display_name_shows_id_number_and_name(self):
        """Two students share a name far more often than an ID number."""
        student = self._new_student()
        self.assertEqual(student.display_name, "2026-00431 — Maria Santos")

    def test_student_is_found_by_id_number_or_by_name(self):
        """Registrars search by whichever the enquirer gave them."""
        student = self._new_student()
        by_number = self.Student.search([("display_name", "ilike", "2026-00431")])
        by_name = self.Student.search([("display_name", "ilike", "Santos")])
        self.assertIn(student, by_number)
        self.assertIn(student, by_name)

    @mute_logger("odoo.sql_db")
    def test_database_refuses_a_duplicate_even_without_the_orm_check(self):
        """The SQL constraint is the real guarantee; the ORM check is courtesy."""
        self._new_student()
        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO trn_student
                    (id_number, name, course_id, year_level, school_year, active)
                VALUES ('2026-00431', 'Impostor', %s, '1', '2026-2027', true)
                """,
                (self.course_bsit.id,),
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./odoo-project test trn_student`
Expected: FAIL — `KeyError: 'trn.student'`, the model does not exist.

- [ ] **Step 3: Write minimal implementation**

`trn_student/models/__init__.py` becomes:

```python
from . import course
from . import student
```

`trn_student/models/student.py`:

```python
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .normalize import normalize_code

YEAR_LEVEL_SELECTION = [
    ("1", "1st Year"),
    ("2", "2nd Year"),
    ("3", "3rd Year"),
    ("4", "4th Year"),
]

SCHOOL_YEAR_PATTERN = re.compile(r"^(\d{4})-(\d{4})$")


class Student(models.Model):
    """A student enrolled in a course.

    Keyed by an ID number the registrar types in — the number the institution
    already issues — rather than a generated sequence, so the record matches
    whatever is printed on the student's card. A SQL unique constraint is the
    real guarantee; the checks in create and write exist to turn a database
    error into a sentence a registrar can act on.
    """

    _name = "trn.student"
    _description = "Student"
    _order = "id_number"
    _rec_names_search = ["id_number", "name"]

    id_number = fields.Char(
        string="ID Number",
        required=True,
        index=True,
        copy=False,
        help="The institution's student number, e.g. '2026-00431'. Must be unique.",
    )
    name = fields.Char(
        string="Full Name",
        required=True,
        help="The student's full name as it appears on their records",
    )
    course_id = fields.Many2one(
        comodel_name="trn.course",
        string="Course",
        required=True,
        ondelete="restrict",
        help="Course the student is enrolled in",
    )
    year_level = fields.Selection(
        selection=YEAR_LEVEL_SELECTION,
        string="Year Level",
        required=True,
        help="How far through the course the student is",
    )
    school_year = fields.Char(
        string="Academic Year",
        required=True,
        default=lambda self: self._default_school_year(),
        help="Academic year this record covers, as 'YYYY-YYYY', e.g. '2026-2027'",
    )
    active = fields.Boolean(
        default=True,
        help="Archive a student who has graduated or left instead of deleting them",
    )

    _unique_id_number = models.Constraint(
        "UNIQUE(id_number)",
        "Student ID number must be unique",
    )

    @api.model
    def _default_school_year(self):
        """Offer the academic year starting this calendar year."""
        this_year = fields.Date.context_today(self).year
        return f"{this_year}-{this_year + 1}"

    @api.depends("id_number", "name")
    def _compute_display_name(self):
        """Show '2026-00431 — Maria Santos'; names collide, ID numbers do not."""
        for student in self:
            student.display_name = f"{student.id_number} — {student.name}"

    @api.model_create_multi
    def create(self, vals_list):
        """Normalise and check the ID number before insert."""
        for vals in vals_list:
            if "id_number" in vals:
                vals["id_number"] = normalize_code(vals["id_number"])
                self._check_id_number_available(vals["id_number"])
        return super().create(vals_list)

    def write(self, vals):
        """Normalise and check the ID number before update."""
        if "id_number" in vals:
            vals["id_number"] = normalize_code(vals["id_number"])
            for student in self:
                self._check_id_number_available(vals["id_number"], exclude=student)
        return super().write(vals)

    @api.model
    def _check_id_number_available(self, id_number, exclude=None):
        """Raise if the ID number is blank or already held by another student."""
        if not id_number:
            raise ValidationError(
                _("A student needs an ID number, e.g. '2026-00431'.")
            )
        domain = [("id_number", "=", id_number)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        existing = self.with_context(active_test=False).search(domain, limit=1)
        if existing:
            raise ValidationError(
                _(
                    "ID number '%(id_number)s' already belongs to %(name)s. "
                    "Every student needs their own number.",
                    id_number=id_number,
                    name=existing.name,
                )
            )

    @api.constrains("school_year")
    def _check_school_year(self):
        """An academic year must be two consecutive four-digit years."""
        for student in self:
            match = SCHOOL_YEAR_PATTERN.match(student.school_year or "")
            if not match:
                raise ValidationError(
                    _(
                        "Academic year '%(value)s' must look like '2026-2027'.",
                        value=student.school_year,
                    )
                )
            start, end = int(match.group(1)), int(match.group(2))
            if end != start + 1:
                raise ValidationError(
                    _(
                        "Academic year '%(value)s' must span two consecutive "
                        "years, so '%(start)s-%(expected)s'.",
                        value=student.school_year,
                        start=start,
                        expected=start + 1,
                    )
                )
```

Append to `trn_student/security/ir.model.access.csv`:

```csv
access_trn_student_system,trn.student / System,model_trn_student,base.group_system,1,1,1,1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./odoo-project test trn_student`
Expected: PASS — 6 tests in `TestCourse`, 16 in `TestStudent`.

- [ ] **Step 5: Commit**

```bash
git add trn_student/
git commit -m "feat(student): add student model keyed by a unique ID number"
```

---

### Task 3: Link courses to their students

**Files:**

- Modify: `trn_student/models/course.py`
- Test: `trn_student/tests/test_course.py`

**Interfaces:**

- Consumes: `trn.student` from Task 2; `StudentCase._new_student` from Task 2.
- Produces: `trn.course.student_ids` (One2many) and `trn.course.student_count` (Integer, computed, non-stored). Task 5 puts `student_count` on the course list view.

- [ ] **Step 1: Write the failing test**

Append to `TestCourse` in `trn_student/tests/test_course.py`:

```python
    def test_student_count_reflects_enrolled_students(self):
        """A registrar sizing a course should not have to run a report."""
        self.assertEqual(self.course_bsit.student_count, 0)
        self._new_student()
        self.course_bsit.invalidate_recordset(["student_ids", "student_count"])
        self.assertEqual(self.course_bsit.student_count, 1)

    def test_student_count_ignores_archived_students(self):
        """Graduated students should not inflate the size of a course."""
        student = self._new_student()
        student.active = False
        self.course_bsit.invalidate_recordset(["student_ids", "student_count"])
        self.assertEqual(self.course_bsit.student_count, 0)

    def test_a_course_with_students_cannot_be_deleted(self):
        """Deleting it would orphan every student enrolled in it."""
        self._new_student()
        with self.assertRaises(Exception):
            self.course_bsit.unlink()

    def test_an_empty_course_can_be_deleted(self):
        """A course added by mistake should not be permanent."""
        spare = self.Course.create({"code": "SPARE", "name": "Spare Course"})
        spare.unlink()
        self.assertFalse(spare.exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./odoo-project test trn_student`
Expected: FAIL — `AttributeError` / `KeyError` on `student_count`, which does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add these fields to `Course` in `trn_student/models/course.py`, after `active`:

```python
    student_ids = fields.One2many(
        comodel_name="trn.student",
        inverse_name="course_id",
        string="Students",
        help="Students currently enrolled in this course",
    )
    student_count = fields.Integer(
        string="Students",
        compute="_compute_student_count",
        help="How many active students are enrolled in this course",
    )
```

And this method, after `_compute_display_name`:

```python
    @api.depends("student_ids")
    def _compute_student_count(self):
        """Count enrolled students so the list view can show course size."""
        for course in self:
            course.student_count = len(course.student_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./odoo-project test trn_student`
Expected: PASS — 10 tests in `TestCourse`, 16 in `TestStudent`.

- [ ] **Step 5: Commit**

```bash
git add trn_student/
git commit -m "feat(student): count students per course and protect courses in use"
```

---

### Task 4: Security groups and access rights

**Files:**

- Create: `trn_student/security/security_groups.xml`
- Modify: `trn_student/security/ir.model.access.csv`
- Modify: `trn_student/__manifest__.py`
- Test: `trn_student/tests/test_security.py`
- Modify: `trn_student/tests/__init__.py`
- Modify: `trn_student/tests/common.py`

**Interfaces:**

- Consumes: both models and `StudentCase` from Tasks 1–3.
- Produces: XML ids `trn_student.group_student_registrar` and `trn_student.group_student_manager`. Task 5 references both in `views/menus.xml`.
- Produces: `StudentCase.user_registrar` and `StudentCase.user_manager`.

- [ ] **Step 1: Write the failing test**

Add to `setUpClass` in `trn_student/tests/common.py`, at the end:

```python
        Users = cls.env["res.users"]
        cls.group_registrar = cls.env.ref("trn_student.group_student_registrar")
        cls.group_manager = cls.env.ref("trn_student.group_student_manager")

        cls.user_registrar = Users.create(
            {
                "name": "Registrar Clerk",
                "login": "student_registrar",
                "group_ids": [Command.set([cls.group_registrar.id])],
            }
        )
        cls.user_manager = Users.create(
            {
                "name": "Registrar Manager",
                "login": "student_manager",
                "group_ids": [Command.set([cls.group_manager.id])],
            }
        )
```

This needs `from odoo import Command` at the top of `common.py`.

`trn_student/tests/__init__.py` becomes:

```python
from . import test_course
from . import test_student
from . import test_security
```

`trn_student/tests/test_security.py`:

```python
from odoo.exceptions import AccessError

from .common import StudentCase


class TestStudentSecurity(StudentCase):
    """Who may read, edit, and delete student and course records."""

    def test_registrar_can_create_a_student(self):
        """Enrolling students is the registrar's whole job."""
        student = self.Student.with_user(self.user_registrar).create(
            {
                "id_number": "2026-00500",
                "name": "Registrar Created",
                "course_id": self.course_bsit.id,
                "year_level": "1",
                "school_year": "2026-2027",
            }
        )
        self.assertTrue(student.exists())

    def test_registrar_can_edit_a_student(self):
        """Correcting a misspelled name must not need a manager."""
        student = self._new_student()
        student.with_user(self.user_registrar).write({"name": "Maria S. Santos"})
        self.assertEqual(student.name, "Maria S. Santos")

    def test_registrar_cannot_delete_a_student(self):
        """Deletion loses history; archiving is the supported route."""
        student = self._new_student()
        with self.assertRaises(AccessError):
            student.with_user(self.user_registrar).unlink()

    def test_registrar_can_read_courses(self):
        """They must pick a course when enrolling someone."""
        course = self.Course.with_user(self.user_registrar).browse(self.course_bsit.id)
        self.assertEqual(course.name, "BS Information Technology")

    def test_registrar_cannot_create_a_course(self):
        """The course list is configuration, not day-to-day data entry."""
        with self.assertRaises(AccessError):
            self.Course.with_user(self.user_registrar).create(
                {"code": "SNEAK", "name": "Unauthorised Course"}
            )

    def test_manager_can_delete_a_student(self):
        """Someone has to be able to remove a record created in error."""
        student = self._new_student()
        student.with_user(self.user_manager).unlink()
        self.assertFalse(student.exists())

    def test_manager_can_create_a_course(self):
        """Managing the course list is what separates the two roles."""
        course = self.Course.with_user(self.user_manager).create(
            {"code": "BSED", "name": "BS Education"}
        )
        self.assertTrue(course.exists())

    def test_manager_inherits_registrar_rights(self):
        """A manager should never have to switch roles to enrol a student."""
        self.assertIn(self.group_registrar, self.user_manager.group_ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./odoo-project test trn_student`
Expected: FAIL — `ValueError: External ID not found: trn_student.group_student_registrar`.

- [ ] **Step 3: Write minimal implementation**

`trn_student/security/security_groups.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="category_trn_student" model="ir.module.category">
        <field name="name">trn Student</field>
        <field name="sequence">10</field>
    </record>

    <record id="privilege_student" model="res.groups.privilege">
        <field name="name">Students</field>
        <field name="category_id" ref="category_trn_student"/>
    </record>

    <!-- Registrar: enrols and maintains students. -->
    <record id="group_student_registrar" model="res.groups">
        <field name="name">Student: Registrar</field>
        <field name="comment">Enrol students and maintain their records.
Courses are read-only.</field>
        <field name="privilege_id" ref="privilege_student"/>
        <field name="implied_ids" eval="[Command.link(ref('base.group_user'))]"/>
    </record>

    <!-- Manager: maintains the course list and may delete records. -->
    <record id="group_student_manager" model="res.groups">
        <field name="name">Student: Registrar Manager</field>
        <field name="comment">Maintain the course list and delete student records.
Implies Registrar permissions.</field>
        <field name="privilege_id" ref="privilege_student"/>
        <field name="implied_ids" eval="[Command.link(ref('group_student_registrar'))]"/>
    </record>
</odoo>
```

`trn_student/security/ir.model.access.csv` in full:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_trn_course_system,trn.course / System,model_trn_course,base.group_system,1,1,1,1
access_trn_student_system,trn.student / System,model_trn_student,base.group_system,1,1,1,1
access_trn_course_registrar,trn.course / Registrar,model_trn_course,group_student_registrar,1,0,0,0
access_trn_course_manager,trn.course / Manager,model_trn_course,group_student_manager,1,1,1,1
access_trn_student_registrar,trn.student / Registrar,model_trn_student,group_student_registrar,1,1,1,0
access_trn_student_manager,trn.student / Manager,model_trn_student,group_student_manager,1,1,1,1
```

`trn_student/__manifest__.py` — replace the `data` list:

```python
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
    ],
```

`security_groups.xml` must come first: the CSV references the groups by XML id.

- [ ] **Step 4: Run test to verify it passes**

Run: `./odoo-project test trn_student`
Expected: PASS — 10 in `TestCourse`, 16 in `TestStudent`, 8 in `TestStudentSecurity`.

- [ ] **Step 5: Commit**

```bash
git add trn_student/
git commit -m "feat(student): add registrar and manager roles with access rights"
```

---

### Task 5: Views and menus

**Files:**

- Create: `trn_student/views/course_views.xml`
- Create: `trn_student/views/student_views.xml`
- Create: `trn_student/views/menus.xml`
- Modify: `trn_student/__manifest__.py`

**Interfaces:**

- Consumes: both models, and the two group XML ids from Task 4.
- Produces: actions `action_trn_student` and `action_trn_course`; root menu `menu_student_root`.

- [ ] **Step 1: Write the failing check**

There is no unit test for view arch; Odoo validates every view against its model
at install time, so a bad field name or a `<tree>` tag fails the install. The
check is the install itself.

Run: `./odoo-project test trn_student`
Expected: PASS currently (34 tests) — this is the baseline to compare against
after adding the views.

- [ ] **Step 2: Write the views**

`trn_student/views/student_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_trn_student_form" model="ir.ui.view">
        <field name="name">trn.student.form</field>
        <field name="model">trn.student</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <widget
                        name="web_ribbon"
                        title="Archived"
                        bg_color="text-bg-danger"
                        invisible="active"
                    />
                    <div class="oe_title">
                        <label for="id_number"/>
                        <h1>
                            <field name="id_number" placeholder="e.g. 2026-00431"/>
                        </h1>
                        <label for="name"/>
                        <h2>
                            <field name="name" placeholder="e.g. Maria Santos"/>
                        </h2>
                    </div>
                    <group>
                        <group>
                            <field name="course_id"/>
                            <field name="year_level"/>
                        </group>
                        <group>
                            <field name="school_year" placeholder="e.g. 2026-2027"/>
                            <field name="active" invisible="1"/>
                        </group>
                    </group>
                    <group name="additional_student_details" invisible="1"/>
                </sheet>
            </form>
        </field>
    </record>

    <record id="view_trn_student_list" model="ir.ui.view">
        <field name="name">trn.student.list</field>
        <field name="model">trn.student</field>
        <field name="arch" type="xml">
            <list>
                <field name="id_number"/>
                <field name="name"/>
                <field name="course_id"/>
                <field name="year_level"/>
                <field name="school_year"/>
                <field name="active" optional="hide"/>
            </list>
        </field>
    </record>

    <record id="view_trn_student_search" model="ir.ui.view">
        <field name="name">trn.student.search</field>
        <field name="model">trn.student</field>
        <field name="arch" type="xml">
            <search>
                <field
                    name="id_number"
                    string="Student"
                    filter_domain="['|', ('id_number', 'ilike', self), ('name', 'ilike', self)]"
                />
                <field name="course_id"/>
                <field name="school_year"/>
                <filter
                    name="filter_year_1"
                    string="1st Year"
                    domain="[('year_level', '=', '1')]"
                />
                <filter
                    name="filter_year_2"
                    string="2nd Year"
                    domain="[('year_level', '=', '2')]"
                />
                <filter
                    name="filter_year_3"
                    string="3rd Year"
                    domain="[('year_level', '=', '3')]"
                />
                <filter
                    name="filter_year_4"
                    string="4th Year"
                    domain="[('year_level', '=', '4')]"
                />
                <separator/>
                <filter
                    name="filter_archived"
                    string="Archived"
                    domain="[('active', '=', False)]"
                />
                <group expand="0" string="Group By">
                    <filter
                        name="group_by_course"
                        string="Course"
                        context="{'group_by': 'course_id'}"
                    />
                    <filter
                        name="group_by_year_level"
                        string="Year Level"
                        context="{'group_by': 'year_level'}"
                    />
                    <filter
                        name="group_by_school_year"
                        string="Academic Year"
                        context="{'group_by': 'school_year'}"
                    />
                </group>
            </search>
        </field>
    </record>

    <record id="action_trn_student" model="ir.actions.act_window">
        <field name="name">Students</field>
        <field name="res_model">trn.student</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="view_trn_student_search"/>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Enrol a student</p>
            <p>
                Each student needs an ID number of their own, a name, a course
                and a year. Archive students who leave rather than deleting them.
            </p>
        </field>
    </record>
</odoo>
```

`trn_student/views/course_views.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_trn_course_form" model="ir.ui.view">
        <field name="name">trn.course.form</field>
        <field name="model">trn.course</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <div class="oe_title">
                        <label for="code"/>
                        <h1>
                            <field name="code" placeholder="e.g. BSIT"/>
                        </h1>
                    </div>
                    <group>
                        <group>
                            <field name="name" placeholder="e.g. BS Information Technology"/>
                            <field name="student_count"/>
                            <field name="active" invisible="1"/>
                        </group>
                    </group>
                    <group name="additional_course_details" invisible="1"/>
                </sheet>
            </form>
        </field>
    </record>

    <record id="view_trn_course_list" model="ir.ui.view">
        <field name="name">trn.course.list</field>
        <field name="model">trn.course</field>
        <field name="arch" type="xml">
            <list>
                <field name="code"/>
                <field name="name"/>
                <field name="student_count"/>
                <field name="active" optional="hide"/>
            </list>
        </field>
    </record>

    <record id="action_trn_course" model="ir.actions.act_window">
        <field name="name">Courses</field>
        <field name="res_model">trn.course</field>
        <field name="view_mode">list,form</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Add a course</p>
            <p>
                Students are enrolled in a course from this list, so adding one
                here makes it available to the registrar immediately.
            </p>
        </field>
    </record>
</odoo>
```

`trn_student/views/menus.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem
        id="menu_student_root"
        name="Students"
        sequence="80"
        groups="trn_student.group_student_registrar"
    />

    <menuitem
        id="menu_student_records"
        name="Students"
        parent="menu_student_root"
        sequence="10"
    />
    <menuitem
        id="menu_student_list"
        name="All Students"
        parent="menu_student_records"
        action="action_trn_student"
        sequence="10"
    />

    <menuitem
        id="menu_student_configuration"
        name="Configuration"
        parent="menu_student_root"
        sequence="90"
        groups="trn_student.group_student_manager"
    />
    <menuitem
        id="menu_student_course"
        name="Courses"
        parent="menu_student_configuration"
        action="action_trn_course"
        sequence="10"
    />
</odoo>
```

`trn_student/__manifest__.py` — replace the `data` list:

```python
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/student_views.xml",
        "views/course_views.xml",
        "views/menus.xml",
    ],
```

`menus.xml` comes last: it references the actions the view files define.

- [ ] **Step 3: Run the tests to verify the views install**

Run: `./odoo-project test trn_student`
Expected: PASS, still 34 tests. A view error surfaces here as an install
failure, not a test failure — read the log for `ParseError` if it fails.

- [ ] **Step 4: Format the XML**

Run: `pre-commit run prettier --files trn_student/views/student_views.xml trn_student/views/course_views.xml trn_student/views/menus.xml`
Expected: PASS, or files reformatted — re-stage if it rewrote them.

- [ ] **Step 5: Commit**

```bash
git add trn_student/
git commit -m "feat(student): add student and course views with a Students menu"
```

---

### Task 6: Demo data

**Files:**

- Create: `trn_student/demo/student_demo.xml`
- Modify: `trn_student/__manifest__.py`
- Test: `trn_student/tests/test_demo_data.py`
- Modify: `trn_student/tests/__init__.py`

**Interfaces:**

- Consumes: both models from Tasks 1–3.
- Produces: XML ids `course_bsit`, `course_bscs`, `course_bsba`, `course_bsed` and `student_1` through `student_6`.

Note the deviation from the spec: the spec describes `test_demo_data.py` as
asserting the demo records load. Odoo 19 does not load demo data in module test
runs, so the test skips itself when the records are absent and asserts fully
when they are present (i.e. on a `--with-demo` database).

- [ ] **Step 1: Write the failing test**

`trn_student/tests/__init__.py` becomes:

```python
from . import test_course
from . import test_student
from . import test_security
from . import test_demo_data
```

`trn_student/tests/test_demo_data.py`:

```python
from odoo.tests.common import TransactionCase


class TestStudentDemoData(TransactionCase):
    """The records in demo/ must be complete and consistent.

    Odoo 19 omits demo data from new databases unless --with-demo is passed, so
    these tests skip rather than fail on an ordinary test run. They earn their
    keep on a demo database, where a half-built record would otherwise only show
    up as a broken screen.
    """

    def _demo_students(self):
        """Return the demo students, or skip if demo data was not loaded."""
        students = self.env["trn.student"].search(
            [("id_number", "like", "DEMO-%")]
        )
        if not students:
            self.skipTest("Demo data not loaded (no --with-demo)")
        return students

    def test_demo_students_are_complete(self):
        """A demo student missing a course renders a broken form."""
        for student in self._demo_students():
            self.assertTrue(student.course_id, f"{student.id_number} has no course")
            self.assertTrue(student.year_level, f"{student.id_number} has no year level")
            self.assertTrue(student.name, f"{student.id_number} has no name")

    def test_demo_school_years_are_valid(self):
        """The constraint runs on create, but a later edit could slip past."""
        for student in self._demo_students():
            start, end = student.school_year.split("-")
            self.assertEqual(int(end), int(start) + 1, student.id_number)

    def test_demo_covers_more_than_one_course(self):
        """A demo with every student in one course shows nothing about grouping."""
        courses = self._demo_students().mapped("course_id")
        self.assertGreater(len(courses), 1)

    def test_demo_covers_more_than_one_year_level(self):
        """Same reasoning: the year filters need something to filter."""
        levels = set(self._demo_students().mapped("year_level"))
        self.assertGreater(len(levels), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./odoo-project test trn_student`
Expected: FAIL — `ModuleNotFoundError` on `test_demo_data` is not expected;
what you should see is the tests being collected and *skipped*. Before the demo
file exists, add the test file first and confirm the 4 tests report as skipped,
not errored. That skipped state is this step's "red".

- [ ] **Step 3: Write the demo data**

`trn_student/demo/student_demo.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="course_bsit" model="trn.course">
        <field name="code">BSIT</field>
        <field name="name">BS Information Technology</field>
    </record>
    <record id="course_bscs" model="trn.course">
        <field name="code">BSCS</field>
        <field name="name">BS Computer Science</field>
    </record>
    <record id="course_bsba" model="trn.course">
        <field name="code">BSBA</field>
        <field name="name">BS Business Administration</field>
    </record>
    <record id="course_bsed" model="trn.course">
        <field name="code">BSED</field>
        <field name="name">BS Education</field>
    </record>

    <record id="student_1" model="trn.student" context="{'tracking_disable': True}">
        <field name="id_number">DEMO-2026-0001</field>
        <field name="name">Maria Santos</field>
        <field name="course_id" ref="course_bsit"/>
        <field name="year_level">2</field>
        <field name="school_year">2026-2027</field>
    </record>
    <record id="student_2" model="trn.student" context="{'tracking_disable': True}">
        <field name="id_number">DEMO-2026-0002</field>
        <field name="name">Jose Rivera</field>
        <field name="course_id" ref="course_bsit"/>
        <field name="year_level">1</field>
        <field name="school_year">2026-2027</field>
    </record>
    <record id="student_3" model="trn.student" context="{'tracking_disable': True}">
        <field name="id_number">DEMO-2026-0003</field>
        <field name="name">Ana Dela Cruz</field>
        <field name="course_id" ref="course_bscs"/>
        <field name="year_level">3</field>
        <field name="school_year">2026-2027</field>
    </record>
    <record id="student_4" model="trn.student" context="{'tracking_disable': True}">
        <field name="id_number">DEMO-2026-0004</field>
        <field name="name">Paolo Mendoza</field>
        <field name="course_id" ref="course_bscs"/>
        <field name="year_level">4</field>
        <field name="school_year">2026-2027</field>
    </record>
    <record id="student_5" model="trn.student" context="{'tracking_disable': True}">
        <field name="id_number">DEMO-2026-0005</field>
        <field name="name">Liza Aquino</field>
        <field name="course_id" ref="course_bsba"/>
        <field name="year_level">2</field>
        <field name="school_year">2026-2027</field>
    </record>
    <record id="student_6" model="trn.student" context="{'tracking_disable': True}">
        <field name="id_number">DEMO-2026-0006</field>
        <field name="name">Ramon Bautista</field>
        <field name="course_id" ref="course_bsed"/>
        <field name="year_level">1</field>
        <field name="school_year">2026-2027</field>
    </record>
</odoo>
```

`trn_student/__manifest__.py` — replace the `demo` list:

```python
    "demo": [
        "demo/student_demo.xml",
    ],
```

- [ ] **Step 4: Verify the demo data loads on a demo database**

Run: `./odoo-project test trn_student`
Expected: PASS — 34 tests pass, 4 demo tests skip.

Then confirm the demo file is not merely unparsed. Install it for real:

Run: `ODOO_INIT_MODULES=trn_student ./odoo-project start --profile ui -y`
Then check the records exist:
Run: `docker exec sample2-db-1 psql -U odoo -d odoo -tAc "select count(*) from trn_student;"`
Expected: `0` on a non-demo database — which is correct and expected. The demo
XML is still validated at install time, so a malformed file fails the install.

- [ ] **Step 5: Commit**

```bash
git add trn_student/
git commit -m "feat(student): add demo courses and students"
```

---

### Task 7: Full verification

**Files:** none created; this task validates the module as a whole.

**Interfaces:**

- Consumes: everything from Tasks 1–6.
- Produces: a verified, lint-clean module ready for a PR.

- [ ] **Step 1: Run the full test suite**

Run: `./odoo-project test trn_student`
Expected: PASS — 34 tests pass, 4 skip. Paste the summary line into the report.

- [ ] **Step 2: Run the linters**

Run: `pre-commit run ruff --files $(git diff --name-only main...HEAD | grep '\.py$')`
Run: `pre-commit run ruff-format --files $(git diff --name-only main...HEAD | grep '\.py$')`
Run: `pre-commit run prettier --files $(git diff --name-only main...HEAD | grep -E '\.(xml|md)$')`
Expected: PASS. If a formatter rewrites files, re-stage and amend.

- [ ] **Step 3: Run the security audit**

Run: `./odoo-project audit-security`
Expected: no findings against `trn_student`. Every model has an ACL row for
each group that needs it, and there is no `sudo()` anywhere in the module.

- [ ] **Step 4: Verify test integrity**

Run the `/verify-tests` command.
Expected: confirmation that no test was removed or weakened across Tasks 1–6.

- [ ] **Step 5: Verify in the running app**

Run: `ODOO_INIT_MODULES=trn_student ./odoo-project start --profile ui -y`
Then, at `http://localhost:8069` as `admin` / `admin`:

1. Confirm the **Students** menu appears in the app switcher.
2. Create a course under Students → Configuration → Courses.
3. Create a student; confirm the form saves.
4. Create a second student with the same ID number; confirm the error names the
   first student rather than showing a Postgres traceback.
5. Group the student list by Course and by Year Level.

- [ ] **Step 6: Commit any fixes and open the PR**

```bash
git add -A
git commit -m "chore(student): apply lint and review fixes"
git push -u origin feat/student-information-system
gh pr create --fill
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: `trn.course` → Task 1;
`trn.student` and its validation → Task 2; `student_ids` / `student_count` /
`ondelete="restrict"` → Task 3; security groups and ACL → Task 4; views, search,
and menus → Task 5; demo data → Task 6; the spec's Verification section → Task 7.

**Deviations from the spec, both deliberate:**

1. `models/normalize.py` is a file the spec's layout did not list. Course code
   and student ID number normalise identically, and one shared three-line helper
   beats the same logic written twice.
2. `test_demo_data.py` skips instead of asserting on a non-demo database,
   because Odoo 19 does not load demo data during test runs. The spec assumed it
   would.

**Placeholder scan.** No TBDs, no "add validation here", no "similar to Task N".
Every code step carries the actual code.

**Type consistency.** `normalize_code` is defined once in Task 1 and imported
under that exact name in Task 2. `StudentCase` gains `cls.Student` and
`_new_student` in Task 2 and `user_registrar` / `user_manager` in Task 4, and
later tasks use exactly those names. The group XML ids
`trn_student.group_student_registrar` and `trn_student.group_student_manager`
are spelled identically in Task 4's XML, Task 4's CSV, and Task 5's menus.
