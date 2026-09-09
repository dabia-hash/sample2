import ast

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.mail.tools.alias_error import AliasError


class ServiceTeam(models.Model):
    """A group of IT staff that handles service requests.

    Teams route work by specialty: the service catalogue names the team that
    normally handles each service, and requests may only be assigned to a
    member of the handling team.

    A team may also own an email address. Mail sent to it opens a request
    routed to that team. The alias mixin is the *optional* variant, so only
    teams actually given an address carry an alias record.
    """

    _name = "trn.service.team"
    _description = "Service Team"
    _inherit = ["mail.alias.mixin.optional"]
    _order = "name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Team name, e.g. 'Network Team'",
    )
    code = fields.Char(
        required=True,
        index=True,
        help="Short unique identifier used by data files, e.g. 'NET'",
    )
    team_lead_id = fields.Many2one(
        comodel_name="res.users",
        string="Team Lead",
        help="Person accountable for the team's queue. Always a member.",
    )
    member_ids = fields.Many2many(
        comodel_name="res.users",
        string="Members",
        help="Staff who may be assigned requests handled by this team",
    )
    default_catalog_id = fields.Many2one(
        comodel_name="trn.service.catalog",
        string="Default Service for Email",
        help="Service applied to requests that arrive by email at this team's "
        "address. Required once the team has an address, because a request "
        "cannot exist without a service.",
    )
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Service team code must be unique",
    )

    def _alias_get_creation_values(self):
        """Point this team's alias at service requests, tagged with the team."""
        values = super()._alias_get_creation_values()
        values["alias_model_id"] = self.env["ir.model"]._get_id("trn.service.request")
        if self.id:
            values["alias_defaults"] = defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults["team_id"] = self.id
        return values

    def _alias_get_error(self, message, message_dict, alias):
        """Refuse inbound mail from anyone who is not a member of staff.

        Rejecting here rather than in message_new matters: the gateway resolves
        this hook against the alias's parent record, which is the team, and a
        non-config error bounces the mail cleanly without flagging the alias
        itself as broken.
        """
        error = super()._alias_get_error(message, message_dict, alias)
        if error:
            return error
        sender = self.env["trn.service.request"]._find_internal_user_from_email(message_dict.get("email_from"))
        if not sender:
            return AliasError(
                "error_service_request_sender_not_internal",
                _("service requests can only be raised from a staff email address"),
            )
        return False

    def _check_alias_has_default_service(self):
        """An addressed team must say which service its email becomes.

        Checked here rather than left to fail at delivery time: without a
        default, an inbound mail would breach catalog_id's required flag deep
        inside the mail gateway, which is a miserable failure to diagnose.

        Called from create() and write() rather than through @api.constrains,
        because the alias mixin assigns alias_id in a nested write of its own.
        A constraint would see that half-applied state and reject a single
        write that sets the address and the default service together - which
        is exactly what saving the form does.
        """
        for team in self:
            if team.alias_id.alias_name and not team.default_catalog_id:
                raise ValidationError(
                    _(
                        "Team '%(team)s' has the email address '%(alias)s' but no default "
                        "service. Choose the service that emails to that address should "
                        "become.",
                        team=team.name,
                        alias=team.alias_id.alias_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Check code uniqueness, then keep the lead inside the member list."""
        for vals in vals_list:
            if vals.get("code"):
                self._check_code_available(vals["code"])
        teams = super().create(vals_list)
        teams._add_lead_to_members()
        teams._check_alias_has_default_service()
        return teams

    def write(self, vals):
        """Check code uniqueness, then keep the lead inside the member list."""
        if vals.get("code"):
            for team in self:
                self._check_code_available(vals["code"], exclude=team)
        result = super().write(vals)
        if "team_lead_id" in vals or "member_ids" in vals:
            self._add_lead_to_members()
        # Skip the alias check on the mixin's own internal alias_id assignment,
        # which happens midway through the caller's write and would otherwise
        # be judged on a half-applied record.
        if set(vals) != {"alias_id"}:
            self._check_alias_has_default_service()
        return result

    @api.model
    def _check_code_available(self, code, exclude=None):
        """Raise if another team already uses this code."""
        domain = [("code", "=", code)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        if self.with_context(active_test=False).search_count(domain):
            raise ValidationError(
                _(
                    "Service team code '%(code)s' is already used by another team. " "Choose a different code.",
                    code=code,
                )
            )

    def _add_lead_to_members(self):
        """A lead must be assignable work on their own team."""
        for team in self:
            if team.team_lead_id and team.team_lead_id not in team.member_ids:
                team.member_ids = [Command.link(team.team_lead_id.id)]
