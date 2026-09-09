from odoo.exceptions import AccessError

from .common import ServiceRequestCase


class TestServiceRequestVisibility(ServiceRequestCase):
    """Record rules: own + office head + IT."""

    def setUp(self):
        super().setUp()
        self.own_request = self._new_request()
        self.colleague_request = self._new_request(requester_id=self.user_colleague.id)
        self.north_request = self._new_request(
            requester_id=self.user_north_requester.id,
            office_id=self.office_north.id,
        )

    def _visible_to(self, user):
        """Requests the given user can actually see."""
        return self.Request.with_user(user).search([])

    def test_requester_sees_their_own_request(self):
        """A requester must be able to track what they raised."""
        self.assertIn(self.own_request, self._visible_to(self.user_requester))

    def test_requester_cannot_see_a_colleague_request(self):
        """An account reset ticket is private to the person who raised it."""
        self.assertNotIn(self.colleague_request, self._visible_to(self.user_requester))

    def test_assignee_sees_a_request_assigned_to_them(self):
        """IT staff must see work pushed to them even without office rights."""
        self.colleague_request.assigned_user_id = self.user_officer
        self.assertIn(self.colleague_request, self._visible_to(self.user_officer))

    def test_office_head_sees_every_request_from_their_office(self):
        """Office heads oversee their own office's demand on IT."""
        visible = self._visible_to(self.user_office_head)
        self.assertIn(self.own_request, visible)
        self.assertIn(self.colleague_request, visible)

    def test_office_head_cannot_see_another_office_requests(self):
        """Oversight stops at the office boundary."""
        self.assertNotIn(self.north_request, self._visible_to(self.user_office_head))

    def test_it_officer_sees_requests_from_every_office(self):
        """IT works the whole queue."""
        visible = self._visible_to(self.user_officer)
        self.assertIn(self.own_request, visible)
        self.assertIn(self.north_request, visible)


class TestServiceRequestPermissions(ServiceRequestCase):
    """Model-level access rights per group."""

    def test_requester_can_raise_a_request(self):
        """Every internal user is allowed to ask IT for help."""
        request = self.Request.with_user(self.user_requester).create(
            {"title": "Printer jam", "catalog_id": self.catalog_account_reset.id}
        )
        self.assertTrue(request.exists())

    def test_requester_cannot_delete_a_request(self):
        """Audit history must survive the requester changing their mind."""
        request = self._new_request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_requester).unlink()

    def test_officer_cannot_delete_a_request(self):
        """Deleting is a manager-only escape hatch."""
        request = self._new_request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_officer).unlink()

    def test_manager_can_delete_a_request(self):
        """Managers can remove records created in error."""
        request = self._new_request()
        request.with_user(self.user_manager).unlink()
        self.assertFalse(request.exists())

    def test_requester_cannot_create_a_catalog_entry(self):
        """The service catalogue is configuration, not user content."""
        with self.assertRaises(AccessError):
            self.Catalog.with_user(self.user_requester).create({"name": "Rogue Service", "code": "ROGUE"})

    def test_officer_cannot_create_a_catalog_entry(self):
        """Officers work tickets; managers configure the catalogue."""
        with self.assertRaises(AccessError):
            self.Catalog.with_user(self.user_officer).create({"name": "Rogue Service", "code": "ROGUE"})

    def test_manager_can_create_a_catalog_entry(self):
        """Managers maintain the offered services."""
        entry = self.Catalog.with_user(self.user_manager).create({"name": "Email Access", "code": "TEST_EMAIL_ACCESS"})
        self.assertTrue(entry.exists())

    def test_requester_can_read_the_catalog(self):
        """Requesters must be able to pick a service when raising a request."""
        entries = self.Catalog.with_user(self.user_requester).search([])
        self.assertIn(self.catalog_account_reset, entries)

    def test_requester_can_read_teams(self):
        """The team shows on the requester's own ticket."""
        teams = self.Team.with_user(self.user_requester).search([])
        self.assertIn(self.team, teams)

    def test_officer_cannot_create_a_team(self):
        """Team structure is manager configuration."""
        with self.assertRaises(AccessError):
            self.Team.with_user(self.user_officer).create({"name": "Rogue", "code": "RG"})
