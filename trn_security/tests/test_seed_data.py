from odoo.tests.common import TransactionCase


class TestSecuritySeedData(TransactionCase):
    """The records shipped in security/ must exist and hang together.

    This module ships no models, only data other modules reference by xml id.
    A missing or renamed record here breaks every module that depends on it at
    install time, so the records are worth asserting directly.
    """

    def test_root_category_is_installed(self):
        """Domain categories hang off this one; without it they are orphans."""
        category = self.env.ref("trn_security.category_trn")
        self.assertEqual(category.name, "Training Sample")

    def test_student_category_sits_under_the_root(self):
        """Categories follow the Training Sample/{Domain} hierarchy."""
        category = self.env.ref("trn_security.category_trn_student")
        self.assertEqual(category.parent_id, self.env.ref("trn_security.category_trn"))

    def test_admin_group_is_installed(self):
        """Domain modules link their manager group into this one."""
        group = self.env.ref("trn_security.group_trn_admin")
        self.assertEqual(group.name, "trn: Administrator")

    def test_admin_group_carries_a_privilege(self):
        """Odoo 19 needs privilege_id to place a group in the user settings UI."""
        group = self.env.ref("trn_security.group_trn_admin")
        self.assertEqual(group.privilege_id, self.env.ref("trn_security.privilege_trn_admin"))

    def test_admin_privilege_sits_in_the_root_category(self):
        """A privilege outside the category tree does not render as expected."""
        privilege = self.env.ref("trn_security.privilege_trn_admin")
        self.assertEqual(privilege.category_id, self.env.ref("trn_security.category_trn"))

    def test_admin_group_implies_internal_user(self):
        """An administrator who is not an internal user cannot log in to the backend."""
        group = self.env.ref("trn_security.group_trn_admin")
        self.assertIn(self.env.ref("base.group_user"), group.implied_ids)
