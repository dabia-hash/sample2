from odoo.exceptions import ValidationError

from .common import StudentCase


class TestFaculty(StudentCase):
    """The professors who teach subject offerings."""

    def test_faculty_code_must_be_unique(self):
        """Two professors sharing a code make every assignment ambiguous."""
        with self.assertRaises(ValidationError):
            self.Faculty.create({"code": self.faculty_reyes.code, "name": "Duplicate"})

    def test_faculty_code_is_uppercased(self):
        """'reyes-j' and 'REYES-J' are the same professor."""
        faculty = self.Faculty.create({"code": "  test cruz m  ", "name": "Prof. Maria Cruz"})
        self.assertEqual(faculty.code, "TEST CRUZ M")

    def test_blank_faculty_code_is_rejected(self):
        """required=True accepts '   '; a professor needs a real code."""
        with self.assertRaises(ValidationError):
            self.Faculty.create({"code": "   ", "name": "Blank"})

    def test_display_name_shows_code_and_name(self):
        """Two professors share a surname more often than a code."""
        self.assertEqual(
            self.faculty_reyes.display_name,
            f"{self.faculty_reyes.code} — {self.faculty_reyes.name}",
        )

    def test_faculty_is_found_by_code_or_by_name(self):
        """Registrars type whichever they remember."""
        by_code = [match[0] for match in self.Faculty.name_search(self.faculty_reyes.code)]
        by_name = [match[0] for match in self.Faculty.name_search("Juan Reyes")]
        self.assertIn(self.faculty_reyes.id, by_code)
        self.assertIn(self.faculty_reyes.id, by_name)

    def test_a_professor_may_have_no_department(self):
        """A visiting lecturer need not belong to a college."""
        faculty = self.Faculty.create({"code": "TEST-VISIT", "name": "Prof. Visiting"})
        self.assertFalse(faculty.department_id)
