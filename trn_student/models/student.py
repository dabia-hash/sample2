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

SEMESTER_SELECTION = [
    ("1", "1st Semester"),
    ("2", "2nd Semester"),
    ("S", "Summer"),
]

# Segment used in the enrollment number, and the short form shown in
# display_name. The selection label itself is too long for a dropdown.
SEMESTER_CODES = {"1": "1ST", "2": "2ND", "S": "SUM"}
SEMESTER_SHORT = {"1": "1st Sem", "2": "2nd Sem", "S": "Summer"}

SCHOOL_YEAR_PATTERN = re.compile(r"^(\d{4})-(\d{4})$")


class Student(models.Model):
    """One admission of a student to one semester.

    This is an admissions ledger, not a student registry: a student who
    enrols for three terms has three rows here, sharing an ID number. That
    ID number is the one the institution already issues, so a record matches
    whatever is printed on the student's card, but on its own it no longer
    identifies a row — the (ID number, academic year, semester) triple does.

    The consequence to keep in mind: nothing structurally forces a student's
    name or course to agree across their own rows. The onchange on id_number
    copies the details forward from their last admission, which makes drift
    unlikely rather than impossible.

    SQL constraints are the real guarantee; the checks in Python exist to
    turn a database error into a sentence a registrar can act on.
    """

    _name = "trn.student"
    _description = "Student"
    _order = "school_year desc, semester, id_number"
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
    semester = fields.Selection(
        selection=SEMESTER_SELECTION,
        string="Semester",
        required=True,
        default="1",
        help="Term this admission covers",
    )
    enrollment_number = fields.Char(
        string="Enrollment ID",
        readonly=True,
        copy=False,
        index=True,
        help="Identifies this admission, e.g. 'ENR/2026-2027/1ST/00042'. Generated on save.",
    )
    school_year = fields.Char(
        string="Academic Year",
        required=True,
        default=lambda self: self._default_school_year(),
        help="Academic year this record covers, as 'YYYY-YYYY', e.g. '2026-2027'",
    )
    is_current_year = fields.Boolean(
        string="Current Academic Year",
        compute="_compute_is_current_year",
        search="_search_is_current_year",
        help="Whether this admission falls in the academic year now running",
    )
    active = fields.Boolean(
        default=True,
        help="Archive a student who has graduated or left instead of deleting them",
    )

    _unique_admission = models.Constraint(
        "UNIQUE(id_number, school_year, semester)",
        "A student can only be admitted once to a given semester",
    )
    _unique_enrollment_number = models.Constraint(
        "UNIQUE(enrollment_number)",
        "Enrollment ID must be unique",
    )

    @api.model
    def _default_school_year(self):
        """Offer the academic year starting this calendar year."""
        this_year = fields.Date.context_today(self).year
        return f"{this_year}-{this_year + 1}"

    @api.depends("school_year")
    def _compute_is_current_year(self):
        """Flag admissions in the academic year now running."""
        current = self._default_school_year()
        for student in self:
            student.is_current_year = student.school_year == current

    def _search_is_current_year(self, operator, value):
        """Search the flag by its underlying academic year.

        Computed without store=True, so the ORM cannot search it directly;
        this turns the filter into a plain domain on school_year.

        Odoo 19 optimises a boolean domain before it reaches here, so
        ('is_current_year', '=', True) arrives as ('in', [True]). Both
        spellings have to be understood.
        """
        if operator in ("in", "not in"):
            wanted = True in value if isinstance(value, list | tuple | set) else bool(value)
            negated = operator == "not in"
        elif operator in ("=", "!="):
            wanted = bool(value)
            negated = operator == "!="
        else:
            raise ValueError(f"Unsupported operator {operator} for is_current_year")
        matches = wanted != negated
        return [("school_year", "=" if matches else "!=", self._default_school_year())]

    @api.depends("id_number", "name", "semester", "school_year")
    def _compute_display_name(self):
        """Show the term too: a student now has one row per semester."""
        for student in self:
            term = SEMESTER_SHORT.get(student.semester, "")
            student.display_name = f"{student.id_number} — {student.name} ({term} {student.school_year})"

    @api.model_create_multi
    def create(self, vals_list):
        """Normalise the ID number and draw an enrollment number before insert."""
        for vals in vals_list:
            if "id_number" in vals:
                vals["id_number"] = normalize_code(vals["id_number"])
                self._check_id_number_present(vals["id_number"])
            # Defaults have not been applied yet, so ask for them: both the
            # duplicate check and the enrollment number need the term.
            filled = self._add_missing_default_values(vals)
            self._check_admission_available(filled.get("id_number"), filled.get("school_year"), filled.get("semester"))
            if not vals.get("enrollment_number"):
                vals["enrollment_number"] = self._next_enrollment_number(
                    filled.get("school_year"), filled.get("semester")
                )
        return super().create(vals_list)

    def write(self, vals):
        """Normalise the ID number and re-check the admission key before update."""
        if "id_number" in vals:
            vals["id_number"] = normalize_code(vals["id_number"])
            self._check_id_number_present(vals["id_number"])
        if {"id_number", "school_year", "semester"} & set(vals):
            for student in self:
                self._check_admission_available(
                    vals.get("id_number", student.id_number),
                    vals.get("school_year", student.school_year),
                    vals.get("semester", student.semester),
                    exclude=student,
                )
        result = super().write(vals)
        if {"school_year", "semester"} & set(vals):
            # The number states the term, so a corrected term needs a new one.
            # Re-entering write here is safe: these keys are not in that call.
            for student in self:
                student.write(
                    {"enrollment_number": self._next_enrollment_number(student.school_year, student.semester)}
                )
        return result

    @api.model
    def _check_id_number_present(self, id_number):
        """Raise if the ID number is blank; required=True lets '   ' through."""
        if not id_number:
            raise ValidationError(_("A student needs an ID number, e.g. '2026-00431'."))

    @api.model
    def _next_enrollment_number(self, school_year, semester):
        """Draw the next number for this term, creating its sequence on first use.

        One static sequence cannot restart its counter per term, so each
        (academic year, term) gets its own — created lazily, under sudo
        because a registrar has no rights on ir.sequence.
        """
        term = SEMESTER_CODES.get(semester, "")
        code = f"trn.student.admission.{school_year}.{term}"
        Sequence = self.env["ir.sequence"].sudo()
        sequence = Sequence.search([("code", "=", code), ("company_id", "=", False)], limit=1)
        if not sequence:
            sequence = Sequence.create(
                {
                    "name": f"Student Admission {school_year} {term}",
                    "code": code,
                    "prefix": f"ENR/{school_year}/{term}/",
                    "padding": 5,
                    "number_increment": 1,
                    "company_id": False,
                }
            )
        return sequence.next_by_id()

    @api.onchange("id_number")
    def _onchange_id_number(self):
        """Carry a returning student's details forward from their last admission."""
        if not self.id_number:
            return
        previous = self.with_context(active_test=False).search(
            [("id_number", "=", normalize_code(self.id_number))],
            order="school_year desc, semester desc",
            limit=1,
        )
        if previous:
            self.name = previous.name
            self.course_id = previous.course_id
            self.year_level = previous.year_level

    @api.model
    def _check_admission_available(self, id_number, school_year, semester, exclude=None):
        """Raise if this student is already admitted to this term.

        Runs before the insert rather than as a constrains: the SQL unique
        constraint would otherwise fire first and hand the registrar a
        Postgres error instead of a sentence they can act on.
        """
        domain = [
            ("id_number", "=", id_number),
            ("school_year", "=", school_year),
            ("semester", "=", semester),
        ]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        duplicate = self.with_context(active_test=False).search(domain, limit=1)
        if duplicate:
            label = dict(SEMESTER_SELECTION).get(semester, "")
            raise ValidationError(
                _(
                    "%(name)s is already admitted to %(term)s under ID number "
                    "'%(id_number)s'. A student is admitted to a term only once.",
                    name=duplicate.name,
                    term=f"{label} {school_year}",
                    id_number=id_number,
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
                        "Academic year '%(value)s' must span two consecutive " "years, so '%(start)s-%(expected)s'.",
                        value=student.school_year,
                        start=start,
                        expected=start + 1,
                    )
                )
