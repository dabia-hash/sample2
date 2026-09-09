from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestOfficeSecurity(TransactionCase):
    """Access control for trn.office.

    Offices are reference data: every internal user must be able to read them
    so office pickers work, but only office managers may maintain them.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Office = cls.env["trn.office"].with_context(tracking_disable=True)
        cls.office = cls.Office.create({"name": "Head Office", "code": "HO"})

        cls.user_basic = cls.env["res.users"].create(
            {
                "name": "Basic User",
                "login": "office_basic",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Office Manager",
                "login": "office_manager",
                "group_ids": [Command.set([cls.env.ref("trn_office.group_office_manager").id])],
            }
        )

    def test_internal_user_can_read_offices(self):
        """Read access is required for office Many2one dropdowns."""
        offices = self.Office.with_user(self.user_basic).search([])
        self.assertIn(self.office, offices)

    def test_internal_user_cannot_create_an_office(self):
        """Ordinary staff must not add offices."""
        with self.assertRaises(AccessError):
            self.Office.with_user(self.user_basic).create({"name": "Rogue", "code": "RG"})

    def test_internal_user_cannot_edit_an_office(self):
        """Ordinary staff must not rename offices."""
        with self.assertRaises(AccessError):
            self.office.with_user(self.user_basic).write({"name": "Renamed"})

    def test_office_manager_can_create_an_office(self):
        """Office managers maintain the office list."""
        office = self.Office.with_user(self.user_manager).create({"name": "New Branch", "code": "NEW"})
        self.assertTrue(office.exists())

    def test_office_manager_can_delete_an_office(self):
        """Office managers can remove an office created in error."""
        office = self.Office.with_user(self.user_manager).create({"name": "Typo", "code": "TYP"})
        office.unlink()
        self.assertFalse(office.exists())
