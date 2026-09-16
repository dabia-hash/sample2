from psycopg2.errors import RestrictViolation

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import StudentCase


class TestDepartment(StudentCase):
    """The grouping a course belongs to, e.g. the College of Computer Studies."""

    def test_department_code_must_be_unique(self):
        """Two departments sharing a code make every course ambiguous."""
        with self.assertRaises(ValidationError):
            self.Department.create({"code": self.department_ccs.code, "name": "Duplicate"})

    def test_department_code_is_uppercased(self):
        """'ccs' and 'CCS' are the same department, so store one spelling."""
        department = self.Department.create({"code": "  test c b a  ", "name": "Test College of Business"})
        self.assertEqual(department.code, "TEST C B A")

    def test_department_code_differing_only_by_case_is_a_duplicate(self):
        """Normalising on write is pointless if it does not close this hole."""
        with self.assertRaises(ValidationError):
            self.Department.create({"code": self.department_ccs.code.lower(), "name": "Sneaky Duplicate"})

    def test_blank_department_code_is_rejected(self):
        """required=True accepts '   '; the registrar must not get away with it."""
        with self.assertRaises(ValidationError):
            self.Department.create({"code": "   ", "name": "Blank"})

    def test_display_name_shows_code_and_name(self):
        """A dropdown of bare codes is unreadable to anyone new."""
        self.assertEqual(
            self.department_ccs.display_name,
            f"{self.department_ccs.code} — {self.department_ccs.name}",
        )

    def test_department_is_found_by_code_or_by_name(self):
        """Registrars type whichever they remember."""
        by_code = [match[0] for match in self.Department.name_search(self.department_ccs.code)]
        by_name = [match[0] for match in self.Department.name_search("Test College of Computer")]
        self.assertIn(self.department_ccs.id, by_code)
        self.assertIn(self.department_ccs.id, by_name)

    def test_course_count_reflects_courses_offered(self):
        """A dean sizing a department should not have to run a report."""
        self.assertEqual(self.department_ccs.course_count, 1)
        self.Course.create(
            {
                "code": "TEST-BSCS",
                "name": "Test BS Computer Science",
                "department_id": self.department_ccs.id,
            }
        )
        self.department_ccs.invalidate_recordset(["course_ids", "course_count"])
        self.assertEqual(self.department_ccs.course_count, 2)

    def test_course_count_ignores_archived_courses(self):
        """A course no longer offered should not inflate its department."""
        self.course_bsit.active = False
        self.department_ccs.invalidate_recordset(["course_ids", "course_count"])
        self.assertEqual(self.department_ccs.course_count, 0)

    @mute_logger("odoo.sql_db")
    def test_a_department_with_courses_cannot_be_deleted(self):
        """Deleting it would orphan every course filed under it."""
        with self.assertRaises(RestrictViolation):
            self.department_ccs.unlink()

    def test_an_empty_department_can_be_deleted(self):
        """A department added by mistake should not be permanent."""
        spare = self.Department.create({"code": "TEST-SPARE-DEPT", "name": "Spare Department"})
        spare.unlink()
        self.assertFalse(spare.exists())

    def test_a_course_belongs_to_a_department(self):
        """The whole point: a course is reachable from its department."""
        self.assertEqual(self.course_bsit.department_id, self.department_ccs)
        self.assertIn(self.course_bsit, self.department_ccs.course_ids)
