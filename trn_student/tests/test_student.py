from psycopg2 import IntegrityError
from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import StudentCase


class TestStudent(StudentCase):
    """The student record, keyed by a hand-entered ID number."""

    def test_a_student_can_be_created(self):
        """The happy path: the four fields the registrar cares about."""
        student = self._new_student()
        self.assertEqual(student.id_number, "TEST-2026-00431")
        self.assertEqual(student.name, "Maria Santos")
        self.assertEqual(student.course_id, self.course_bsit)
        self.assertEqual(student.year_level, "2")
        self.assertEqual(student.school_year, "2026-2027")

    def test_duplicate_id_number_is_rejected(self):
        """The ID number is the key; two students cannot share one."""
        self._new_student()
        with self.assertRaises(ValidationError):
            self._new_student(name="Impostor")

    def test_id_number_differing_only_by_whitespace_is_a_duplicate(self):
        """A stray space must not buy a second record for the same student."""
        self._new_student()
        with self.assertRaises(ValidationError):
            self._new_student(id_number="  TEST-2026-00431 ", name="Impostor")

    def test_id_number_differing_only_by_case_is_a_duplicate(self):
        """Same reasoning as whitespace: 'a-1' and 'A-1' are one number."""
        self._new_student(id_number="test-tr-7")
        with self.assertRaises(ValidationError):
            self._new_student(id_number="TEST-TR-7", name="Impostor")

    def test_blank_id_number_is_rejected(self):
        """required=True lets '   ' through; the key must be real."""
        with self.assertRaises(ValidationError):
            self._new_student(id_number="   ")

    def test_id_number_is_normalised_on_write(self):
        """Renumbering a student goes through the same normalisation."""
        student = self._new_student()
        student.write({"id_number": "  TEST-2026-00999 "})
        self.assertEqual(student.id_number, "TEST-2026-00999")

    def test_school_year_accepts_consecutive_years(self):
        """The ordinary case the registrar types every day."""
        student = self._new_student(school_year="2030-2031")
        self.assertEqual(student.school_year, "2030-2031")

    def test_school_year_rejects_a_gap(self):
        """'2026-2030' is a typo, not a four-year enrolment."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="2026-2030")

    def test_school_year_rejects_a_backwards_range(self):
        """The second year must follow the first."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="2026-2025")

    def test_school_year_rejects_the_wrong_separator(self):
        """One format keeps grouping and sorting meaningful."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="2026/2027")

    def test_school_year_rejects_two_digit_years(self):
        """'26-27' sorts and groups wrongly against four-digit years."""
        with self.assertRaises(ValidationError):
            self._new_student(school_year="26-27")

    @mute_logger("odoo.sql_db")
    def test_course_is_required(self):
        """A student with no course cannot be scheduled or reported on."""
        with self.assertRaises(NotNullViolation):
            self._new_student(course_id=False)

    @mute_logger("odoo.sql_db")
    def test_year_level_is_required(self):
        """Year level drives nearly every registrar filter."""
        with self.assertRaises(NotNullViolation):
            self._new_student(year_level=False)

    def test_display_name_shows_id_number_and_name(self):
        """Two students share a name far more often than an ID number."""
        student = self._new_student()
        self.assertEqual(student.display_name, "TEST-2026-00431 — Maria Santos")

    def test_student_is_found_by_id_number_or_by_name(self):
        """Registrars search by whichever the enquirer gave them."""
        student = self._new_student()
        by_number = [match[0] for match in self.Student.name_search("TEST-2026-00431")]
        by_name = [match[0] for match in self.Student.name_search("Santos")]
        self.assertIn(student.id, by_number)
        self.assertIn(student.id, by_name)

    @mute_logger("odoo.sql_db")
    def test_database_refuses_a_duplicate_even_without_the_orm_check(self):
        """The SQL constraint is the real guarantee; the ORM check is courtesy."""
        self._new_student()
        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO trn_student
                    (id_number, name, course_id, year_level, school_year, active)
                VALUES ('TEST-2026-00431', 'Impostor', %s, '1', '2026-2027', true)
                """,
                (self.course_bsit.id,),
            )
