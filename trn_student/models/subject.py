from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .normalize import normalize_code


class Subject(models.Model):
    """One subject the institution teaches, e.g. IT101 Programming 1.

    The catalogue entry is timeless: IT101 means the same thing every year.
    Who teaches it and who takes it belong to a trn.subject.offering, one per
    term, so the same subject can be taught by different professors in
    different semesters without the catalogue changing.
    """

    _name = "trn.subject"
    _description = "Subject"
    _order = "code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        required=True,
        index=True,
        help="Short identifier for the subject, e.g. 'IT101'. Stored uppercase.",
    )
    name = fields.Char(
        required=True,
        translate=True,
        help="Subject as it appears on records, e.g. 'Programming 1'",
    )
    units = fields.Float(
        required=True,
        default=3.0,
        digits=(3, 1),
        help="Credit units the subject carries, e.g. 3.0",
    )
    department_id = fields.Many2one(
        comodel_name="trn.department",
        string="Department",
        ondelete="restrict",
        help="Department that owns this subject. Optional: general-education " "subjects are taught across colleges.",
    )
    active = fields.Boolean(
        default=True,
        help="Archive a subject no longer taught instead of deleting it",
    )
    offering_ids = fields.One2many(
        comodel_name="trn.subject.offering",
        inverse_name="subject_id",
        string="Offerings",
        help="Terms in which this subject has been offered",
    )
    offering_count = fields.Integer(
        string="Offering Count",
        compute="_compute_offering_count",
        help="How many terms this subject is offered in",
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Subject code must be unique",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        """Show 'IT101 — Programming 1' rather than a bare code."""
        for subject in self:
            subject.display_name = f"{subject.code} — {subject.name}"

    @api.depends("offering_ids")
    def _compute_offering_count(self):
        """Count offerings so the list view can show how often it runs."""
        for subject in self:
            subject.offering_count = len(subject.offering_ids)

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
            for subject in self:
                self._check_code_available(vals["code"], exclude=subject)
        return super().write(vals)

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if the code is blank or already taken by another subject."""
        if not code:
            raise ValidationError(_("A subject needs a code, e.g. 'IT101'."))
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        existing = self.with_context(active_test=False).search(domain, limit=1)
        if existing:
            raise ValidationError(
                _(
                    "Subject code '%(code)s' is already used by '%(name)s'. Choose a different code.",
                    code=code,
                    name=existing.name,
                )
            )
