from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import StudentCase


class TestCourse(StudentCase):
    """The master list of courses offered."""

    def test_course_code_must_be_unique(self):
        """Two courses sharing a code make every student ambiguous."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": self.course_bsit.code, "name": "Duplicate"})

    def test_course_code_is_uppercased(self):
        """'bsit' and 'BSIT' are the same course, so store one spelling."""
        course = self.Course.create({"code": "  test bs cs  ", "name": "Test BS Computer Science"})
        self.assertEqual(course.code, "TEST BS CS")

    def test_course_code_differing_only_by_case_is_a_duplicate(self):
        """Normalising on write is pointless if it does not close this hole."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": self.course_bsit.code.lower(), "name": "Sneaky Duplicate"})

    def test_blank_course_code_is_rejected(self):
        """required=True accepts '   '; the registrar must not get away with it."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "   ", "name": "Blank"})

    def test_display_name_shows_code_and_name(self):
        """A dropdown of bare codes is unreadable to anyone new."""
        self.assertEqual(
            self.course_bsit.display_name,
            f"{self.course_bsit.code} — {self.course_bsit.name}",
        )

    def test_course_is_found_by_code_or_by_name(self):
        """Registrars type whichever they remember."""
        by_code = [match[0] for match in self.Course.name_search(self.course_bsit.code)]
        by_name = [match[0] for match in self.Course.name_search("Test BS Information")]
        self.assertIn(self.course_bsit.id, by_code)
        self.assertIn(self.course_bsit.id, by_name)

    def test_student_count_reflects_enrolled_students(self):
        """A registrar sizing a course should not have to run a report."""
        self.assertEqual(self.course_bsit.student_count, 0)
        self._new_student()
        self.course_bsit.invalidate_recordset(["student_ids", "student_count"])
        self.assertEqual(self.course_bsit.student_count, 1)

    def test_student_count_ignores_archived_students(self):
        """Graduated students should not inflate the size of a course."""
        student = self._new_student()
        student.active = False
        self.course_bsit.invalidate_recordset(["student_ids", "student_count"])
        self.assertEqual(self.course_bsit.student_count, 0)

    @mute_logger("odoo.sql_db")
    def test_a_course_with_students_cannot_be_deleted(self):
        """Deleting it would orphan every student enrolled in it."""
        self._new_student()
        with self.assertRaises(Exception):
            self.course_bsit.unlink()

    def test_an_empty_course_can_be_deleted(self):
        """A course added by mistake should not be permanent."""
        spare = self.Course.create({"code": "TEST-SPARE", "name": "Spare Course"})
        spare.unlink()
        self.assertFalse(spare.exists())
