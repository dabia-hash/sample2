from odoo import Command
from odoo.tests.common import TransactionCase


class StudentCase(TransactionCase):
    """Shared fixtures: one course, plus a registrar and a manager.

    The two users mirror the security matrix, so access tests exercise the
    real groups rather than admin's blanket rights.

    Fixture codes carry a TEST- prefix because course codes are unique across
    the database: a bare "BSIT" here collides with the demo course of the same
    code and breaks every test class on a --with-demo database.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Course = cls.env["trn.course"]
        cls.Student = cls.env["trn.student"]

        cls.course_bsit = cls.Course.create(
            {"code": "TEST-BSIT", "name": "Test BS Information Technology"}
        )

        Users = cls.env["res.users"]
        cls.group_registrar = cls.env.ref("trn_student.group_student_registrar")
        cls.group_manager = cls.env.ref("trn_student.group_student_manager")

        cls.user_registrar = Users.create(
            {
                "name": "Registrar Clerk",
                "login": "student_registrar",
                "group_ids": [Command.set([cls.group_registrar.id])],
            }
        )
        cls.user_manager = Users.create(
            {
                "name": "Registrar Manager",
                "login": "student_manager",
                "group_ids": [Command.set([cls.group_manager.id])],
            }
        )

    @classmethod
    def _new_student(cls, **overrides):
        """Create a second-year test-course student unless told otherwise."""
        values = {
            "id_number": "TEST-2026-00431",
            "name": "Maria Santos",
            "course_id": cls.course_bsit.id,
            "year_level": "2",
            "school_year": "2026-2027",
        }
        values.update(overrides)
        return cls.Student.create(values)
