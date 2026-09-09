from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .service_priority import CATEGORY_VOCABULARY_URI, PRIORITY_SELECTION


class ServiceCatalog(models.Model):
    """One IT service the organisation offers.

    The catalogue is configuration, not code: an IT manager adds a service in
    the UI and it becomes available to requesters immediately, carrying its own
    default team, default priority, and target resolution time.
    """

    _name = "trn.service.catalog"
    _description = "Service Catalog Entry"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Service as the requester sees it, e.g. 'Account Reset'",
    )
    code = fields.Char(
        required=True,
        index=True,
        help="Short unique identifier used by data files, e.g. 'ACCOUNT_RESET'",
    )
    category_id = fields.Many2one(
        comodel_name="trn.vocabulary.code",
        string="Category",
        domain=[("namespace_uri", "=", CATEGORY_VOCABULARY_URI)],
        ondelete="restrict",
        help="Grouping used for reporting, e.g. Access, Network, Hardware",
    )
    default_team_id = fields.Many2one(
        comodel_name="trn.service.team",
        string="Default Team",
        help="Team that normally handles this service. Applied to new requests.",
    )
    default_priority = fields.Selection(
        selection=PRIORITY_SELECTION,
        string="Default Priority",
        default="normal",
        required=True,
        help="Priority applied to new requests for this service",
    )
    target_resolution_hours = fields.Integer(
        string="Target Resolution (hours)",
        default=24,
        required=True,
        help="Hours from submission within which this service should be resolved. "
        "Drives the request deadline and the overdue flag.",
    )
    description = fields.Text(
        translate=True,
        help="Guidance shown to requesters about what this service covers",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Service code must be unique",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Check code uniqueness before insert."""
        for vals in vals_list:
            if vals.get("code"):
                self._check_code_available(vals["code"])
        return super().create(vals_list)

    def write(self, vals):
        """Check code uniqueness before update."""
        if vals.get("code"):
            for entry in self:
                self._check_code_available(vals["code"], exclude=entry)
        return super().write(vals)

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if another catalogue entry already uses this code."""
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        if self.with_context(active_test=False).search_count(domain):
            raise ValidationError(
                _(
                    "Service code '%(code)s' is already used by another service. " "Choose a different code.",
                    code=code,
                )
            )

    @api.constrains("target_resolution_hours")
    def _check_target_resolution_hours(self):
        """A non-positive target would put the deadline at or before submission."""
        for entry in self:
            if entry.target_resolution_hours <= 0:
                raise ValidationError(
                    _(
                        "Target resolution time for '%(name)s' must be at least one hour.",
                        name=entry.name,
                    )
                )
