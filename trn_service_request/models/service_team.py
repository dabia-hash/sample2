from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class ServiceTeam(models.Model):
    """A group of IT staff that handles service requests.

    Teams route work by specialty: the service catalogue names the team that
    normally handles each service, and requests may only be assigned to a
    member of the handling team.
    """

    _name = "trn.service.team"
    _description = "Service Team"
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
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Service team code must be unique",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Check code uniqueness, then keep the lead inside the member list."""
        for vals in vals_list:
            if vals.get("code"):
                self._check_code_available(vals["code"])
        teams = super().create(vals_list)
        teams._add_lead_to_members()
        return teams

    def write(self, vals):
        """Check code uniqueness, then keep the lead inside the member list."""
        if vals.get("code"):
            for team in self:
                self._check_code_available(vals["code"], exclude=team)
        result = super().write(vals)
        if "team_lead_id" in vals or "member_ids" in vals:
            self._add_lead_to_members()
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
