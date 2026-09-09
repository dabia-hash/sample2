import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Office(models.Model):
    """A place of work that raises and owns operational records.

    Offices are organisational reference data, deliberately independent of
    hr.department and res.company so that any module can scope a record to an
    office without pulling in the HR app or multi-company machinery.
    """

    _name = "trn.office"
    _description = "Office"
    _order = "name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Human-readable office name, e.g. 'Head Office'",
    )
    code = fields.Char(
        required=True,
        index=True,
        help="Short unique identifier used by data files and reports, e.g. 'HO'",
    )
    parent_id = fields.Many2one(
        comodel_name="trn.office",
        string="Parent Office",
        ondelete="restrict",
        index=True,
        help="Office this one reports to, for organisations with branch structures",
    )
    child_ids = fields.One2many(
        comodel_name="trn.office",
        inverse_name="parent_id",
        string="Sub-Offices",
    )
    office_head_id = fields.Many2one(
        comodel_name="res.users",
        string="Office Head",
        help="Person accountable for this office. Office heads can see every " "record raised by their office.",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Address",
        help="Contact record holding the office's physical address",
    )
    active = fields.Boolean(
        default=True,
        help="Set to inactive to retire an office without losing its history",
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Office code must be unique",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Check code uniqueness before insert.

        Runs before super() so users see a readable ValidationError instead of
        a raw IntegrityError from the UNIQUE constraint.
        """
        for vals in vals_list:
            if vals.get("code"):
                self._check_code_available(vals["code"])
        return super().create(vals_list)

    def write(self, vals):
        """Check code uniqueness before update."""
        if vals.get("code"):
            for office in self:
                self._check_code_available(vals["code"], exclude=office)
        return super().write(vals)

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if another office already uses this code."""
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        if self.with_context(active_test=False).search_count(domain):
            raise ValidationError(
                _(
                    "Office code '%(code)s' is already used by another office. " "Choose a different code.",
                    code=code,
                )
            )

    @api.constrains("parent_id")
    def _check_office_hierarchy(self):
        """An office cannot sit beneath itself."""
        if self._has_cycle():
            raise ValidationError(_("An office cannot be its own parent or ancestor."))

    @api.depends("name", "code")
    def _compute_display_name(self):
        """Show the code alongside the name so pickers stay unambiguous."""
        for office in self:
            office.display_name = f"[{office.code}] {office.name}" if office.code else office.name
