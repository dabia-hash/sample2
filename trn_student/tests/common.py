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

        cls.Department = cls.env["trn.department"]
        cls.Subject = cls.env["trn.subject"]
        cls.Faculty = cls.env["trn.faculty"]
        cls.Offering = cls.env["trn.subject.offering"]
        cls.Grade = cls.env["trn.grade"]
        cls.Course = cls.env["trn.course"]
        cls.Student = cls.env["trn.student"]

        cls.department_ccs = cls.Department.create({"code": "TEST-CCS", "name": "Test College of Computer Studies"})
        cls.course_bsit = cls.Course.create(
            {
                "code": "TEST-BSIT",
                "name": "Test BS Information Technology",
                "department_id": cls.department_ccs.id,
            }
        )

        cls.subject_it101 = cls.Subject.create({"code": "TEST-IT101", "name": "Test Programming 1", "units": 3.0})
        cls.faculty_reyes = cls.Faculty.create({"code": "TEST-REYES", "name": "Prof. Juan Reyes"})
        cls.offering_it101 = cls.Offering.create(
            {
                "subject_id": cls.subject_it101.id,
                "school_year": "2026-2027",
                "semester": "1",
                "faculty_id": cls.faculty_reyes.id,
            }
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

    @classmethod
    def _new_offering(cls, **overrides):
        """Create another offering of the test subject unless told otherwise."""
        values = {
            "subject_id": cls.subject_it101.id,
            "school_year": "2026-2027",
            "semester": "1",
            "faculty_id": cls.faculty_reyes.id,
        }
        values.update(overrides)
        return cls.Offering.create(values)

    @classmethod
    def _new_subject(cls, code, **overrides):
        """Create another subject, so a student can take more than one."""
        values = {"code": code, "name": f"Test Subject {code}", "units": 3.0}
        values.update(overrides)
        return cls.Subject.create(values)

    @classmethod
    def _new_grade(cls, student=None, offering=None, **overrides):
        """Enrol a student in an offering; grade stays blank unless given."""
        values = {
            "student_id": (student or cls._new_student()).id,
            "offering_id": (offering or cls.offering_it101).id,
        }
        values.update(overrides)
        return cls.Grade.create(values)
