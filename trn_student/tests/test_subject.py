from odoo.exceptions import ValidationError

from .common import StudentCase


class TestSubject(StudentCase):
    """The catalogue of subjects the institution teaches."""

    def test_subject_code_must_be_unique(self):
        """Two subjects sharing a code make every grade ambiguous."""
        with self.assertRaises(ValidationError):
            self.Subject.create({"code": self.subject_it101.code, "name": "Duplicate"})

    def test_subject_code_is_uppercased(self):
        """'it101' and 'IT101' are the same subject, so store one spelling."""
        subject = self.Subject.create({"code": "  test math 1  ", "name": "Test College Algebra"})
        self.assertEqual(subject.code, "TEST MATH 1")

    def test_subject_code_differing_only_by_case_is_a_duplicate(self):
        """Normalising on write is pointless if it does not close this hole."""
        with self.assertRaises(ValidationError):
            self.Subject.create({"code": self.subject_it101.code.lower(), "name": "Sneaky"})

    def test_blank_subject_code_is_rejected(self):
        """required=True accepts '   '; a subject needs a real code."""
        with self.assertRaises(ValidationError):
            self.Subject.create({"code": "   ", "name": "Blank"})

    def test_display_name_shows_code_and_name(self):
        """A dropdown of bare codes is unreadable to anyone new."""
        self.assertEqual(
            self.subject_it101.display_name,
            f"{self.subject_it101.code} — {self.subject_it101.name}",
        )

    def test_subject_is_found_by_code_or_by_name(self):
        """Registrars type whichever they remember."""
        by_code = [match[0] for match in self.Subject.name_search(self.subject_it101.code)]
        by_name = [match[0] for match in self.Subject.name_search("Test Programming")]
        self.assertIn(self.subject_it101.id, by_code)
        self.assertIn(self.subject_it101.id, by_name)

    def test_subject_defaults_to_three_units(self):
        """Most subjects are three units; typing it every time is noise."""
        subject = self.Subject.create({"code": "TEST-DEFAULT", "name": "Test Default Units"})
        self.assertEqual(subject.units, 3.0)

    def test_a_subject_may_have_no_department(self):
        """General-education subjects span colleges, so it stays optional."""
        subject = self.Subject.create({"code": "TEST-GENED", "name": "Test General Education"})
        self.assertFalse(subject.department_id)
