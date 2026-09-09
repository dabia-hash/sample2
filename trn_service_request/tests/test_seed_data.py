from odoo.tests.common import TransactionCase

from ..models.service_priority import (
    CATEGORY_VOCABULARY_URI,
    PRIORITY_SELECTION,
    PRIORITY_VOCABULARY_URI,
)


class TestServiceRequestSeedData(TransactionCase):
    """The records shipped in data/ must be complete and self-consistent.

    These load on every install, unlike demo data, which Odoo 19 omits from new
    databases unless --with-demo is passed.
    """

    def test_request_sequence_is_installed(self):
        """Without the sequence, every new request would be numbered 'New'."""
        sequence = self.env["ir.sequence"].search([("code", "=", "trn.service.request")])
        self.assertTrue(sequence)

    def test_seeded_services_are_installed(self):
        """The module ships the services the organisation already offers."""
        account_reset = self.env.ref("trn_service_request.catalog_account_reset")
        network_failure = self.env.ref("trn_service_request.catalog_network_failure")
        self.assertTrue(account_reset.active)
        self.assertTrue(network_failure.active)

    def test_every_seeded_service_can_route_and_schedule(self):
        """A service without a team or target time cannot route or be chased."""
        for entry in self.env["trn.service.catalog"].search([]):
            self.assertTrue(entry.default_team_id, f"{entry.code} has no default team")
            self.assertTrue(entry.category_id, f"{entry.code} has no category")
            self.assertGreater(entry.target_resolution_hours, 0, f"{entry.code} target")

    def test_priority_vocabulary_covers_every_selection_value(self):
        """Each priority must resolve to a code, or reporting loses rows."""
        codes = self.env["trn.vocabulary.code"]
        for value, _label in PRIORITY_SELECTION:
            self.assertTrue(
                codes.get_code(PRIORITY_VOCABULARY_URI, value),
                f"priority '{value}' has no vocabulary code",
            )

    def test_category_vocabulary_is_installed(self):
        """Service categories drive the reporting group-by."""
        categories = self.env["trn.vocabulary.code"].search([("namespace_uri", "=", CATEGORY_VOCABULARY_URI)])
        self.assertTrue(categories)

    def test_a_request_on_a_seeded_service_derives_its_priority_code(self):
        """The derived priority code is what makes both representations agree."""
        request = self.env["trn.service.request"].create(
            {
                "title": "Seeded service smoke test",
                "catalog_id": self.env.ref("trn_service_request.catalog_account_reset").id,
            }
        )
        self.assertEqual(request.priority, "high")
        self.assertEqual(request.priority_code_id.code, "high")
