from odoo.tests.common import TransactionCase


class StudentCase(TransactionCase):
    """Shared fixtures: one course to hang students off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Course = cls.env["trn.course"]

        cls.course_bsit = cls.Course.create({"code": "BSIT", "name": "BS Information Technology"})
