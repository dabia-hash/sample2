from odoo.exceptions import ValidationError

from .common import ServiceRequestCase


class TestServiceCatalog(ServiceRequestCase):
    """The configurable list of offered IT services."""

    def test_catalog_code_must_be_unique(self):
        """Codes identify services to data files and integrations."""
        with self.assertRaises(ValidationError):
            self.Catalog.create({"name": "Duplicate", "code": self.catalog_account_reset.code})

    def test_target_resolution_hours_must_be_positive(self):
        """A non-positive target would produce a deadline at or before submission."""
        with self.assertRaises(ValidationError):
            self.Catalog.create({"name": "Broken", "code": "BROKEN", "target_resolution_hours": 0})

    def test_catalog_supplies_the_default_team(self):
        """Choosing a service routes the request without manual triage."""
        request = self._new_request()
        self.assertEqual(request.team_id, self.team)

    def test_catalog_supplies_the_default_priority(self):
        """Account resets are urgent by configuration, not by habit."""
        request = self._new_request()
        self.assertEqual(request.priority, "high")

    def test_an_explicit_priority_overrides_the_catalog_default(self):
        """Configuration sets the default; the requester can still disagree."""
        request = self._new_request(priority="urgent")
        self.assertEqual(request.priority, "urgent")

    def test_changing_the_service_reroutes_an_untouched_request(self):
        """Correcting the service during triage should re-apply its defaults."""
        network_team = self.Team.create({"name": "Network Team", "code": "NET"})
        network = self.Catalog.create(
            {
                "name": "Network Failure",
                "code": "TEST_NETWORK_FAILURE",
                "default_team_id": network_team.id,
                "target_resolution_hours": 2,
            }
        )
        request = self._new_request()
        request.catalog_id = network
        self.assertEqual(request.team_id, network_team)

    def test_seeded_services_are_installed(self):
        """The module ships the services the organisation already offers."""
        account_reset = self.env.ref("trn_service_request.catalog_account_reset")
        network_failure = self.env.ref("trn_service_request.catalog_network_failure")
        self.assertTrue(account_reset.active)
        self.assertTrue(network_failure.active)


class TestServiceTeam(ServiceRequestCase):
    """IT teams that handle requests."""

    def test_team_code_must_be_unique(self):
        """Team codes are referenced by data files."""
        with self.assertRaises(ValidationError):
            self.Team.create({"name": "Duplicate", "code": "ACCT"})

    def test_team_lead_is_automatically_a_member(self):
        """A lead must be assignable work on their own team."""
        team = self.Team.create({"name": "Hardware Team", "code": "HW", "team_lead_id": self.user_officer.id})
        self.assertIn(self.user_officer, team.member_ids)
