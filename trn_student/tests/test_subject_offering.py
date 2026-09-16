from psycopg2.errors import NotNullViolation, RestrictViolation

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import StudentCase


class TestSubjectOffering(StudentCase):
    """One subject, taught in one term, by one professor."""

    def test_an_offering_can_be_created(self):
        """The happy path: a subject placed in a term with a professor."""
        offering = self.offering_it101
        self.assertEqual(offering.subject_id, self.subject_it101)
        self.assertEqual(offering.school_year, "2026-2027")
        self.assertEqual(offering.semester, "1")
        self.assertEqual(offering.faculty_id, self.faculty_reyes)

    def test_a_subject_is_offered_once_per_term(self):
        """Two offerings of one subject in one term split the class list."""
        with self.assertRaises(ValidationError):
            self._new_offering()

    def test_the_same_subject_may_be_offered_in_another_term(self):
        """IT101 runs every semester; that is the point of an offering."""
        second = self._new_offering(semester="2")
        self.assertNotEqual(second, self.offering_it101)
        self.assertEqual(second.subject_id, self.offering_it101.subject_id)

    def test_the_same_subject_may_be_offered_in_a_later_year(self):
        """Next year's IT101 is a separate offering with its own class."""
        later = self._new_offering(school_year="2027-2028")
        self.assertNotEqual(later, self.offering_it101)

    def test_display_name_shows_the_subject_and_the_term(self):
        """An offering picker listing bare subject codes is ambiguous."""
        self.assertEqual(
            self.offering_it101.display_name,
            "TEST-IT101 — Test Programming 1 (1st Sem 2026-2027)",
        )

    def test_academic_year_must_look_like_a_school_year(self):
        """The same rule an admission follows, so the two can be compared."""
        with self.assertRaises(ValidationError):
            self._new_offering(semester="2", school_year="2026/2027")

    def test_academic_year_rejects_a_gap(self):
        """'2026-2030' is a typo, not a four-year offering."""
        with self.assertRaises(ValidationError):
            self._new_offering(semester="2", school_year="2026-2030")

    @mute_logger("odoo.sql_db")
    def test_semester_is_required(self):
        """An offering with no term cannot be matched to an admission."""
        with self.assertRaises(NotNullViolation):
            self._new_offering(semester=False)

    def test_a_professor_may_be_assigned_later(self):
        """Offerings are published before they are staffed; TBA is normal."""
        offering = self._new_offering(semester="S", faculty_id=False)
        self.assertFalse(offering.faculty_id)

    def test_offering_count_reflects_the_terms_a_subject_runs_in(self):
        """A dean planning load should not have to run a report."""
        self.assertEqual(self.subject_it101.offering_count, 1)
        self._new_offering(semester="2")
        self.subject_it101.invalidate_recordset(["offering_ids", "offering_count"])
        self.assertEqual(self.subject_it101.offering_count, 2)

    def test_offering_count_reflects_a_professors_teaching_load(self):
        """Same reasoning, from the professor's side."""
        self.assertEqual(self.faculty_reyes.offering_count, 1)
        self._new_offering(semester="2")
        self.faculty_reyes.invalidate_recordset(["offering_ids", "offering_count"])
        self.assertEqual(self.faculty_reyes.offering_count, 2)

    @mute_logger("odoo.sql_db")
    def test_a_subject_that_has_been_offered_cannot_be_deleted(self):
        """Deleting it would orphan every offering and its grades."""
        with self.assertRaises(RestrictViolation):
            self.subject_it101.unlink()

    @mute_logger("odoo.sql_db")
    def test_a_professor_with_offerings_cannot_be_deleted(self):
        """Deleting them would silently unstaff a running class."""
        with self.assertRaises(RestrictViolation):
            self.faculty_reyes.unlink()

    def test_a_new_offering_has_no_students(self):
        """The class list starts empty and fills as students enrol."""
        self.assertEqual(self.offering_it101.student_count, 0)
