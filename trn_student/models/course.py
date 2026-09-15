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
                    "Course code '%(code)s' is already used by '%(name)s'. " "Choose a different code.",
                    code=code,
                    name=existing.name,
                )
            )
