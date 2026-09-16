from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .normalize import normalize_code


class Faculty(models.Model):
    """A professor who can be assigned to teach a subject offering.

    Deliberately a small model of its own rather than hr.employee, which
    would install the whole HR app, or res.partner, which is shared with
    every other kind of contact. This module stays on base and trn_security.
    """

    _name = "trn.faculty"
    _description = "Faculty"
    _order = "code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        required=True,
        index=True,
        help="Short identifier for the professor, e.g. 'REYES-J'. Stored uppercase.",
    )
    name = fields.Char(
        required=True,
        help="Professor's name as it appears on class records, e.g. 'Prof. Juan Reyes'",
    )
    department_id = fields.Many2one(
        comodel_name="trn.department",
        string="Department",
        ondelete="restrict",
        help="College the professor belongs to. Optional: a visiting lecturer " "need not belong to one.",
    )
    active = fields.Boolean(
        default=True,
        help="Archive a professor who has left instead of deleting them",
    )
    offering_ids = fields.One2many(
        comodel_name="trn.subject.offering",
        inverse_name="faculty_id",
        string="Offerings",
        help="Subject offerings this professor teaches",
    )
    offering_count = fields.Integer(
        string="Offering Count",
        compute="_compute_offering_count",
        help="How many offerings this professor currently teaches",
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Faculty code must be unique",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        """Show 'REYES-J — Prof. Juan Reyes'; surnames collide, codes do not."""
        for faculty in self:
            faculty.display_name = f"{faculty.code} — {faculty.name}"

    @api.depends("offering_ids")
    def _compute_offering_count(self):
        """Count offerings so a manager can see teaching load at a glance."""
        for faculty in self:
            faculty.offering_count = len(faculty.offering_ids)

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
            for faculty in self:
                self._check_code_available(vals["code"], exclude=faculty)
        return super().write(vals)

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if the code is blank or already taken by another professor."""
        if not code:
            raise ValidationError(_("A professor needs a code, e.g. 'REYES-J'."))
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        existing = self.with_context(active_test=False).search(domain, limit=1)
        if existing:
            raise ValidationError(
                _(
                    "Faculty code '%(code)s' is already used by '%(name)s'. Choose a different code.",
                    code=code,
                    name=existing.name,
                )
            )
