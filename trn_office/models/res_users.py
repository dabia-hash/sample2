from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    office_id = fields.Many2one(
        comodel_name="trn.office",
        string="Office",
        help="Office this person works in. Used as the default office on " "records they create.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        """Let a user read their own office.

        Without this, defaulting a record's office from the current user raises
        an AccessError for ordinary staff, because Odoo restricts which fields a
        non-privileged user may read on their own res.users record.
        """
        return super().SELF_READABLE_FIELDS + ["office_id"]
