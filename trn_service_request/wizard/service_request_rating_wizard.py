from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.service_priority import RATING_SELECTION


class ServiceRequestRatingWizard(models.TransientModel):
    """Lets a requester score a closed request.

    The rating is written with elevated rights because a requester's record
    rule stops them editing their request once it leaves the New state. Rather
    than widen that rule - which cannot restrict which fields are written - the
    wizard verifies the caller is the requester and the request is closed, then
    writes only the two rating fields.
    """

    _name = "trn.service.request.rating.wizard"
    _description = "Rate a Service Request"

    request_id = fields.Many2one(
        comodel_name="trn.service.request",
        string="Request",
        required=True,
        readonly=True,
    )
    rating_value = fields.Selection(
        selection=RATING_SELECTION,
        string="Satisfaction",
        required=True,
    )
    rating_comment = fields.Text(
        string="Comment",
        help="Optional feedback for the IT team",
    )

    @api.model
    def default_get(self, fields_list):
        """Pick up the request the wizard was opened from."""
        result = super().default_get(fields_list)
        if self.env.context.get("active_model") == "trn.service.request":
            result["request_id"] = self.env.context.get("active_id")
        return result

    def action_submit_rating(self):
        """Validate the caller, then record the score on the request."""
        self.ensure_one()
        # Read with elevated rights so that an unauthorised caller gets a clear
        # explanation instead of an opaque AccessError from the record rules.
        # Every branch below re-checks authorisation before anything is written,
        # and the write is limited to the two rating fields.
        # nosemgrep: odoo-sudo-without-context
        request = self.request_id.sudo()

        if request.requester_id != self.env.user:
            raise UserError(_("Only the person who raised a request can rate it."))
        if request.state != "closed":
            raise UserError(_("%(name)s can only be rated once it is closed.") % {"name": request.name})
        if request.rating_value:
            raise UserError(_("%(name)s has already been rated.") % {"name": request.name})

        request.write(
            {
                "rating_value": self.rating_value,
                "rating_comment": self.rating_comment,
            }
        )
        return {"type": "ir.actions.act_window_close"}
