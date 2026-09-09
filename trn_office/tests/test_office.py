from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestOffice(TransactionCase):
    """Behaviour of the trn.office model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Office = cls.env["trn.office"].with_context(tracking_disable=True)

    def test_office_code_must_be_unique(self):
        """Two offices cannot share a code, and the user sees a readable error."""
        self.Office.create({"name": "Head Office", "code": "HO"})
        with self.assertRaises(ValidationError):
            self.Office.create({"name": "Duplicate", "code": "HO"})

    def test_renaming_a_code_onto_an_existing_one_is_rejected(self):
        """The uniqueness check also guards writes, not just creates."""
        self.Office.create({"name": "Head Office", "code": "HO"})
        branch = self.Office.create({"name": "North Branch", "code": "NB"})
        with self.assertRaises(ValidationError):
            branch.code = "HO"

    def test_display_name_is_prefixed_with_the_code(self):
        """Offices show as '[CODE] Name' so codes are visible in dropdowns."""
        office = self.Office.create({"name": "North Branch", "code": "NB"})
        self.assertEqual(office.display_name, "[NB] North Branch")

    def test_office_is_active_when_created(self):
        """New offices are usable without an extra activation step."""
        office = self.Office.create({"name": "South Branch", "code": "SB"})
        self.assertTrue(office.active)

    def test_archived_office_is_excluded_from_default_search(self):
        """Archiving keeps history but removes the office from pickers."""
        office = self.Office.create({"name": "Closed Branch", "code": "CB"})
        office.active = False
        self.assertNotIn(office, self.Office.search([("code", "=", "CB")]))

    def test_office_cannot_be_its_own_ancestor(self):
        """A cycle in the office hierarchy is rejected."""
        parent = self.Office.create({"name": "Head Office", "code": "HO"})
        child = self.Office.create({"name": "Branch", "code": "BR", "parent_id": parent.id})
        with self.assertRaises(ValidationError):
            parent.parent_id = child

    def test_user_can_be_assigned_a_home_office(self):
        """res.users carries the office a person raises requests for."""
        office = self.Office.create({"name": "Head Office", "code": "HO"})
        user = self.env["res.users"].create({"name": "Office Staff", "login": "office_staff", "office_id": office.id})
        self.assertEqual(user.office_id, office)
