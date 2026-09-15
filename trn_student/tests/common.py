from odoo.tests.common import TransactionCase


class StudentCase(TransactionCase):
    """Shared fixtures: one course to hang students off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Course = cls.env["trn.course"]
        cls.Student = cls.env["trn.student"]

        cls.course_bsit = cls.Course.create({"code": "BSIT", "name": "BS Information Technology"})

    @classmethod
    def _new_student(cls, **overrides):
        """Create a second-year BSIT student unless told otherwise."""
        values = {
            "id_number": "2026-00431",
            "name": "Maria Santos",
            "course_id": cls.course_bsit.id,
            "year_level": "2",
            "school_year": "2026-2027",
        }
        values.update(overrides)
        return cls.Student.create(values)
