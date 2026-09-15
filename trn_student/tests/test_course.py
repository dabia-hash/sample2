from odoo.exceptions import ValidationError

from .common import StudentCase


class TestCourse(StudentCase):
    """The master list of courses offered."""

    def test_course_code_must_be_unique(self):
        """Two courses sharing a code make every student ambiguous."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "BSIT", "name": "Duplicate"})

    def test_course_code_is_uppercased(self):
        """'bsit' and 'BSIT' are the same course, so store one spelling."""
        course = self.Course.create({"code": "  bs cs  ", "name": "BS Computer Science"})
        self.assertEqual(course.code, "BS CS")

    def test_course_code_differing_only_by_case_is_a_duplicate(self):
        """Normalising on write is pointless if it does not close this hole."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "bsit", "name": "Sneaky Duplicate"})

    def test_blank_course_code_is_rejected(self):
        """required=True accepts '   '; the registrar must not get away with it."""
        with self.assertRaises(ValidationError):
            self.Course.create({"code": "   ", "name": "Blank"})

    def test_display_name_shows_code_and_name(self):
        """A dropdown of bare codes is unreadable to anyone new."""
        self.assertEqual(self.course_bsit.display_name, "BSIT — BS Information Technology")

    def test_course_is_found_by_code_or_by_name(self):
        """Registrars type whichever they remember."""
        by_code = [match[0] for match in self.Course.name_search("BSIT")]
        by_name = [match[0] for match in self.Course.name_search("Information")]
        self.assertIn(self.course_bsit.id, by_code)
        self.assertIn(self.course_bsit.id, by_name)
