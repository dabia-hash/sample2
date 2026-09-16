from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .normalize import normalize_code


class Department(models.Model):
    """A grouping of courses, e.g. the College of Computer Studies.

    Departments are configuration a manager maintains in the UI. They exist so
    courses can be filed and reported on by college without the department
    being retyped — and misspelled — on every course.
    """

    _name = "trn.department"
    _description = "Department"
    _order = "code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        required=True,
        index=True,
        help="Short identifier for the department, e.g. 'CCS'. Stored uppercase.",
    )
    name = fields.Char(
        required=True,
        translate=True,
        help="Department as it appears on records, e.g. 'College of Computer Studies'",
    )
    active = fields.Boolean(
        default=True,
        help="Archive a department that no longer exists instead of deleting it",
    )
    course_ids = fields.One2many(
        comodel_name="trn.course",
        inverse_name="department_id",
        string="Courses",
        help="Courses this department offers",
    )
    course_count = fields.Integer(
        string="Course Count",
        compute="_compute_course_count",
        help="How many active courses this department offers",
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Department code must be unique",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        """Show 'CCS — College of Computer Studies' rather than a bare code."""
        for department in self:
            department.display_name = f"{department.code} — {department.name}"

    @api.depends("course_ids")
    def _compute_course_count(self):
        """Count courses offered so the list view can show department size."""
        for department in self:
            department.course_count = len(department.course_ids)

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
            for department in self:
                self._check_code_available(vals["code"], exclude=department)
        return super().write(vals)

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if the code is blank or already taken by another department."""
        if not code:
            raise ValidationError(_("A department needs a code, e.g. 'CCS'."))
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        existing = self.with_context(active_test=False).search(domain, limit=1)
        if existing:
            raise ValidationError(
                _(
                    "Department code '%(code)s' is already used by '%(name)s'. " "Choose a different code.",
                    code=code,
                    name=existing.name,
                )
            )
