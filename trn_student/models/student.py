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
            raise ValidationError(_("A student needs an ID number, e.g. '2026-00431'."))
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
                        "Academic year '%(value)s' must span two consecutive " "years, so '%(start)s-%(expected)s'.",
                        value=student.school_year,
                        start=start,
                        expected=start + 1,
                    )
                )
