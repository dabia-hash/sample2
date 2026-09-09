from odoo import Command
from odoo.tests.common import TransactionCase


class ServiceRequestCase(TransactionCase):
    """Shared fixtures: two offices, one team, one catalogue entry, five users.

    The user set mirrors the security matrix: an ordinary requester in each
    office, the head of one office, an IT officer, and an IT manager.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Request = cls.env["trn.service.request"]
        cls.Catalog = cls.env["trn.service.catalog"]
        cls.Team = cls.env["trn.service.team"]
        Office = cls.env["trn.office"]
        Users = cls.env["res.users"]

        cls.office_head_quarters = Office.create({"name": "Head Office", "code": "HO"})
        cls.office_north = Office.create({"name": "North Branch", "code": "NB"})

        cls.group_user = cls.env.ref("trn_service_request.group_service_request_user")
        cls.group_office_head = cls.env.ref("trn_service_request.group_service_request_supervisor")
        cls.group_officer = cls.env.ref("trn_service_request.group_service_request_officer")
        cls.group_manager = cls.env.ref("trn_service_request.group_service_request_manager")

        cls.user_requester = Users.create(
            {
                "name": "Head Office Requester",
                "login": "sr_requester_ho",
                "office_id": cls.office_head_quarters.id,
                "group_ids": [Command.set([cls.group_user.id])],
            }
        )
        cls.user_colleague = Users.create(
            {
                "name": "Head Office Colleague",
                "login": "sr_colleague_ho",
                "office_id": cls.office_head_quarters.id,
                "group_ids": [Command.set([cls.group_user.id])],
            }
        )
        cls.user_north_requester = Users.create(
            {
                "name": "North Branch Requester",
                "login": "sr_requester_nb",
                "office_id": cls.office_north.id,
                "group_ids": [Command.set([cls.group_user.id])],
            }
        )
        cls.user_office_head = Users.create(
            {
                "name": "Head Office Head",
                "login": "sr_head_ho",
                "office_id": cls.office_head_quarters.id,
                "group_ids": [Command.set([cls.group_office_head.id])],
            }
        )
        cls.user_officer = Users.create(
            {
                "name": "IT Officer",
                "login": "sr_officer",
                "office_id": cls.office_head_quarters.id,
                "group_ids": [Command.set([cls.group_officer.id])],
            }
        )
        cls.user_manager = Users.create(
            {
                "name": "IT Manager",
                "login": "sr_manager",
                "office_id": cls.office_head_quarters.id,
                "group_ids": [Command.set([cls.group_manager.id])],
            }
        )

        cls.office_head_quarters.office_head_id = cls.user_office_head

        cls.team = cls.Team.create(
            {
                "name": "Accounts Team",
                "code": "ACCT",
                "team_lead_id": cls.user_manager.id,
                "member_ids": [Command.set([cls.user_officer.id, cls.user_manager.id])],
            }
        )
        cls.catalog_account_reset = cls.Catalog.create(
            {
                "name": "Account Reset",
                "code": "TEST_ACCOUNT_RESET",
                "default_team_id": cls.team.id,
                "default_priority": "high",
                "target_resolution_hours": 4,
            }
        )

    @classmethod
    def _new_request(cls, **overrides):
        """Create a request as the Head Office requester unless told otherwise."""
        values = {
            "title": "Cannot log in",
            "description": "Locked out after password change.",
            "requester_id": cls.user_requester.id,
            "catalog_id": cls.catalog_account_reset.id,
        }
        values.update(overrides)
        return cls.Request.create(values)
