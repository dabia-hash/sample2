import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import email_normalize, html2plaintext

from .service_priority import (
    OPEN_STATES,
    PRIORITY_SELECTION,
    PRIORITY_VOCABULARY_URI,
    RATING_SELECTION,
)

_logger = logging.getLogger(__name__)


class ServiceRequest(models.Model):
    """An IT service request raised by a member of staff.

    Moves through New -> Assigned -> In Progress -> Resolved -> Closed, and may
    be cancelled at any point before closure. The chosen catalogue entry drives
    routing (team), urgency (priority) and the resolution deadline.
    """

    _name = "trn.service.request"
    _description = "Service Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submitted_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: _("New"),
        help="Human-quotable reference drawn from a sequence",
    )
    title = fields.Char(
        required=True,
        tracking=True,
        help="One-line summary of the problem",
    )
    description = fields.Text(
        help="What happened, what was expected, and anything already tried",
    )

    requester_id = fields.Many2one(
        comodel_name="res.users",
        string="Requester",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help="Person who raised the request",
    )
    office_id = fields.Many2one(
        comodel_name="trn.office",
        string="Office",
        compute="_compute_office_id",
        store=True,
        readonly=False,
        tracking=True,
        help="Office the request comes from. Defaults to the requester's office " "and drives office-head visibility.",
    )

    catalog_id = fields.Many2one(
        comodel_name="trn.service.catalog",
        string="Service",
        required=True,
        ondelete="restrict",
        tracking=True,
        help="Service being requested. Sets the handling team, priority and deadline.",
    )
    category_id = fields.Many2one(
        comodel_name="trn.vocabulary.code",
        string="Category",
        related="catalog_id.category_id",
        store=True,
        help="Reporting category, taken from the service",
    )

    priority = fields.Selection(
        selection=PRIORITY_SELECTION,
        compute="_compute_priority",
        store=True,
        readonly=False,
        tracking=True,
        help="Urgency of the request. Defaults from the service and can be overridden.",
    )
    priority_code_id = fields.Many2one(
        comodel_name="trn.vocabulary.code",
        string="Priority Code",
        compute="_compute_priority_code_id",
        store=True,
        help="Vocabulary code derived from the priority, for reporting and "
        "integrations. Derived rather than entered, so the two cannot disagree.",
    )

    team_id = fields.Many2one(
        comodel_name="trn.service.team",
        string="Team",
        compute="_compute_team_id",
        store=True,
        readonly=False,
        tracking=True,
        help="Team handling the request. Defaults from the service.",
    )
    team_member_ids = fields.Many2many(
        comodel_name="res.users",
        string="Team Members",
        related="team_id.member_ids",
        help="Members of the handling team. Narrows the assignee picker in the "
        "form; the real enforcement is _check_assignee_is_team_member.",
    )
    assigned_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Assigned To",
        tracking=True,
        help="IT staff member doing the work. Must belong to the handling team.",
    )

    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("assigned", "Assigned"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="new",
        required=True,
        tracking=True,
        copy=False,
    )

    submitted_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        copy=False,
        help="When the request was raised. Anchors the resolution deadline.",
    )
    assigned_date = fields.Datetime(readonly=True, copy=False)
    resolved_date = fields.Datetime(readonly=True, copy=False)
    closed_date = fields.Datetime(readonly=True, copy=False)
    deadline_date = fields.Datetime(
        string="Target Resolution",
        compute="_compute_deadline_date",
        store=True,
        help="Submission time plus the service's target resolution hours",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="Still owed work and past the target resolution time",
    )

    resolution = fields.Text(
        help="What was done to resolve the request. Required before resolving.",
    )
    rating_value = fields.Selection(
        selection=RATING_SELECTION,
        string="Satisfaction",
        readonly=True,
        copy=False,
        help="Score left by the requester after closure",
    )
    rating_comment = fields.Text(
        string="Satisfaction Comment",
        readonly=True,
        copy=False,
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("requester_id")
    def _compute_office_id(self):
        """Default the office to wherever the requester works."""
        for request in self:
            request.office_id = request.requester_id.office_id

    @api.depends("catalog_id")
    def _compute_priority(self):
        """Take the service's default urgency."""
        for request in self:
            request.priority = request.catalog_id.default_priority or "normal"

    @api.depends("catalog_id")
    def _compute_team_id(self):
        """Route to the team that normally handles this service."""
        for request in self:
            request.team_id = request.catalog_id.default_team_id

    @api.depends("priority")
    def _compute_priority_code_id(self):
        """Mirror the priority onto its vocabulary code for reporting."""
        codes = self.env["trn.vocabulary.code"]
        for request in self:
            request.priority_code_id = (
                codes.get_code(PRIORITY_VOCABULARY_URI, request.priority) if request.priority else False
            )

    @api.depends("submitted_date", "catalog_id.target_resolution_hours")
    def _compute_deadline_date(self):
        """Deadline is the target resolution time after submission."""
        for request in self:
            hours = request.catalog_id.target_resolution_hours
            if request.submitted_date and hours:
                request.deadline_date = request.submitted_date + timedelta(hours=hours)
            else:
                request.deadline_date = False

    @api.depends("deadline_date", "state")
    def _compute_is_overdue(self):
        """Overdue means still owed work, not merely slow in the past."""
        now = fields.Datetime.now()
        for request in self:
            request.is_overdue = bool(
                request.deadline_date and request.state in OPEN_STATES and request.deadline_date < now
            )

    def _search_is_overdue(self, operator, value):
        """Make the Overdue search filter work on a non-stored field."""
        if operator not in ("=", "!="):
            raise UserError(_("The Overdue filter only supports '=' and '!='."))
        looking_for_overdue = (operator == "=") == bool(value)
        now = fields.Datetime.now()
        if looking_for_overdue:
            return [("deadline_date", "<", now), ("state", "in", OPEN_STATES)]
        return [
            "|",
            "|",
            ("deadline_date", "=", False),
            ("deadline_date", ">=", now),
            ("state", "not in", OPEN_STATES),
        ]

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("assigned_user_id", "team_id")
    def _check_assignee_is_team_member(self):
        """Work cannot be pushed onto someone outside the handling team."""
        for request in self:
            if not request.assigned_user_id or not request.team_id:
                continue
            if request.assigned_user_id not in request.team_id.member_ids:
                raise ValidationError(
                    _(
                        "%(user)s is not a member of the %(team)s team and cannot be "
                        "assigned this request. Add them to the team first.",
                        user=request.assigned_user_id.name,
                        team=request.team_id.name,
                    )
                )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Number the request from a sequence and follow the requester."""
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("trn.service.request") or _("New")
        requests = super().create(vals_list)
        for request in requests:
            if request.requester_id.partner_id:
                request.message_subscribe(partner_ids=request.requester_id.partner_id.ids)
        return requests

    # ------------------------------------------------------------------
    # Email intake
    # ------------------------------------------------------------------

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Open a request from an inbound email sent to a team's address.

        Only known internal users may raise a request this way. Mail from
        anyone else is refused outright rather than parked under a catch-all
        account, so an outsider cannot fill the queue.
        """
        values = dict(custom_values or {})
        sender = self._find_internal_user_from_email(msg_dict.get("email_from"))
        if not sender:
            raise ValueError("Service request email refused: sender does not match an active " "internal user.")

        team = self.env["trn.service.team"].browse(values.get("team_id"))
        if not team.default_catalog_id:
            raise ValueError("Service request email refused: the addressed team has no default service.")

        subject = (msg_dict.get("subject") or "").strip()
        values.update(
            {
                "requester_id": sender.id,
                "title": subject or _("Email request from %(name)s", name=sender.name),
                "description": html2plaintext(msg_dict.get("body") or ""),
                "catalog_id": team.default_catalog_id.id,
                # mail.thread.message_new drops the subject into _rec_name -
                # here the sequence reference - whenever that key is falsy, so
                # a blank would be overwritten with the subject line. Passing
                # the same sentinel the field defaults to keeps numbering in
                # create(), the single place that draws an SR/ number.
                "name": _("New"),
            }
        )
        return super().message_new(msg_dict, values)

    def message_update(self, msg_dict, update_vals=None):
        """Thread a reply onto the request without letting email drive it.

        An inbound email is a comment, not a command: it must never move the
        workflow or overwrite what IT recorded.
        """
        protected = {
            "state",
            "priority",
            "resolution",
            "assigned_user_id",
            "team_id",
            "catalog_id",
            "rating_value",
            "rating_comment",
        }
        safe_vals = {key: value for key, value in (update_vals or {}).items() if key not in protected}
        return super().message_update(msg_dict, safe_vals)

    @api.model
    def _find_internal_user_from_email(self, email_from):
        """Resolve an email address to an active, non-portal internal user."""
        normalized = email_normalize(email_from) if email_from else False
        if not normalized:
            return self.env["res.users"]
        user = self.env["res.users"].search(
            [
                ("email_normalized", "=", normalized),
                ("share", "=", False),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not user:
            # Deliberately logs the address only, never the message body.
            _logger.warning("Service request email from unknown sender %s ignored", normalized)
        return user

    # ------------------------------------------------------------------
    # Lifecycle actions
    # ------------------------------------------------------------------

    def action_assign(self):
        """Take the request out of triage and give it an owner."""
        for request in self:
            if request.state != "new":
                raise UserError(
                    _("Only a new request can be assigned. %(name)s is %(state)s.")
                    % {"name": request.name, "state": request.state}
                )
            if not request.assigned_user_id:
                raise UserError(_("Choose who will handle %(name)s before assigning it.") % {"name": request.name})
            request._pre_assign_hook()
            request.write({"state": "assigned", "assigned_date": fields.Datetime.now()})
            if request.assigned_user_id.partner_id:
                request.message_subscribe(partner_ids=request.assigned_user_id.partner_id.ids)
        return True

    def action_start(self):
        """Record that work has actually begun."""
        for request in self:
            if request.state != "assigned":
                raise UserError(
                    _("Only an assigned request can be started. %(name)s is %(state)s.")
                    % {"name": request.name, "state": request.state}
                )
            request.state = "in_progress"
        return True

    def action_resolve(self):
        """Mark the work done, with a note saying what was done."""
        for request in self:
            if request.state not in ("assigned", "in_progress"):
                raise UserError(
                    _("Only a request being worked on can be resolved. %(name)s is %(state)s.")
                    % {"name": request.name, "state": request.state}
                )
            if not request.resolution:
                raise UserError(_("Describe how %(name)s was resolved before resolving it.") % {"name": request.name})
            request.write({"state": "resolved", "resolved_date": fields.Datetime.now()})
            request._post_resolve_hook()
        return True

    def action_close(self):
        """Close a resolved request."""
        for request in self:
            if request.state != "resolved":
                raise UserError(
                    _("Only a resolved request can be closed. %(name)s is %(state)s.")
                    % {"name": request.name, "state": request.state}
                )
            request.write({"state": "closed", "closed_date": fields.Datetime.now()})
        return True

    def action_cancel(self):
        """Cancel a request raised in error."""
        for request in self:
            if request.state in ("closed", "cancelled"):
                raise UserError(
                    _("%(name)s is already %(state)s and cannot be cancelled.")
                    % {"name": request.name, "state": request.state}
                )
            request.state = "cancelled"
        return True

    def action_open_rating_wizard(self):
        """Open the satisfaction wizard for this request."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rate this service"),
            "res_model": "trn.service.request.rating.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_model": self._name, "active_id": self.id},
        }

    # ------------------------------------------------------------------
    # Extension hooks
    # ------------------------------------------------------------------

    def _pre_assign_hook(self):
        """Override to add validation before a request is assigned."""

    def _post_resolve_hook(self):
        """Notify the requester that their request has been resolved."""
        template = self.env.ref(
            "trn_service_request.mail_template_request_resolved",
            raise_if_not_found=False,
        )
        if not template:
            return
        # Sending a notification is a system action on behalf of the officer,
        # who has no rights on mail.mail. The recipient is fixed by the template
        # to the requester, so this cannot be used to mail arbitrary addresses,
        # and no caller-supplied data reaches the elevated call.
        # nosemgrep: odoo-sudo-without-context
        template.sudo().send_mail(self.id, force_send=False)
