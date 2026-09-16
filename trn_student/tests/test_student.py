from psycopg2 import IntegrityError
from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tests import Form
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

    def test_duplicate_admission_for_the_same_term_is_rejected(self):
        """A student cannot be admitted to the same term twice."""
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

    def test_display_name_shows_id_number_name_and_term(self):
        """A student now has a row per term; the term tells them apart."""
        student = self._new_student()
        self.assertEqual(
            student.display_name,
            "TEST-2026-00431 — Maria Santos (1st Sem 2026-2027)",
        )

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
                    (id_number, name, course_id, year_level, school_year,
                     semester, enrollment_number, active)
                VALUES ('TEST-2026-00431', 'Impostor', %s, '1', '2026-2027',
                        '1', 'ENR/TEST/RAW/00001', true)
                """,
                (self.course_bsit.id,),
            )


class TestAdmission(StudentCase):
    """A student is admitted once per semester, and each admission is numbered."""

    ENROLLMENT_PATTERN = r"^ENR/\d{4}-\d{4}/(1ST|2ND|SUM)/\d{5}$"

    def test_semester_defaults_to_the_first(self):
        """Most admissions are keyed in at the start of the academic year."""
        self.assertEqual(self._new_student().semester, "1")

    def test_the_same_student_can_be_admitted_to_two_semesters(self):
        """The whole point: enrolment recurs, so the ledger holds a row per term."""
        first = self._new_student(semester="1")
        second = self._new_student(semester="2")
        self.assertNotEqual(first, second)
        self.assertEqual(first.id_number, second.id_number)

    def test_the_same_term_in_a_later_year_is_a_separate_admission(self):
        """A repeating student is admitted to 1st Sem again the following year."""
        first = self._new_student(school_year="2026-2027")
        second = self._new_student(school_year="2027-2028")
        self.assertNotEqual(first, second)

    def test_a_second_admission_to_the_same_term_is_rejected(self):
        """Keying the same student in twice for one term is the common slip."""
        self._new_student(semester="2")
        with self.assertRaises(ValidationError):
            self._new_student(semester="2", name="Duplicate Entry")

    def test_the_rejection_names_the_student_and_the_term(self):
        """A bare constraint violation tells a registrar nothing actionable."""
        self._new_student(semester="1")
        with self.assertRaises(ValidationError) as caught:
            self._new_student(semester="1")
        message = str(caught.exception)
        self.assertIn("Maria Santos", message)
        self.assertIn("1st Semester 2026-2027", message)

    def test_enrollment_number_is_generated(self):
        """The registrar never types it; it identifies the admission."""
        student = self._new_student()
        self.assertRegex(student.enrollment_number, self.ENROLLMENT_PATTERN)

    def test_enrollment_number_carries_the_academic_year_and_term(self):
        """Readable at a glance beats opening the record to find the term."""
        first = self._new_student(semester="1")
        second = self._new_student(semester="2")
        summer = self._new_student(semester="S")
        self.assertTrue(first.enrollment_number.startswith("ENR/2026-2027/1ST/"))
        self.assertTrue(second.enrollment_number.startswith("ENR/2026-2027/2ND/"))
        self.assertTrue(summer.enrollment_number.startswith("ENR/2026-2027/SUM/"))

    def test_enrollment_numbers_increment_within_a_term(self):
        """Two admissions to one term must not collide."""
        first = self._new_student(id_number="TEST-A-1")
        second = self._new_student(id_number="TEST-A-2")
        self.assertEqual(
            int(second.enrollment_number.rsplit("/", 1)[1]),
            int(first.enrollment_number.rsplit("/", 1)[1]) + 1,
        )

    def test_each_term_counts_separately(self):
        """The counter restarts per academic year and term, so each gets a sequence."""
        self._new_student(semester="1")
        self._new_student(semester="2")
        codes = self.env["ir.sequence"].search([("code", "like", "trn.student.admission.2026-2027.")]).mapped("code")
        self.assertIn("trn.student.admission.2026-2027.1ST", codes)
        self.assertIn("trn.student.admission.2026-2027.2ND", codes)

    def test_enrollment_number_is_not_reused_by_a_copy(self):
        """Duplicating a record must draw a fresh number, not clone one."""
        student = self._new_student()
        duplicate = student.copy({"id_number": "TEST-COPY-1"})
        self.assertNotEqual(duplicate.enrollment_number, student.enrollment_number)

    @mute_logger("odoo.sql_db")
    def test_the_database_refuses_a_duplicate_enrollment_number(self):
        """The SQL constraint is the real guarantee behind the sequence."""
        student = self._new_student()
        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO trn_student
                    (id_number, name, course_id, year_level, school_year,
                     semester, enrollment_number, active)
                VALUES ('TEST-CLASH-1', 'Clash', %s, '1', '2026-2027', 'S', %s, true)
                """,
                (self.course_bsit.id, student.enrollment_number),
            )

    def test_readmitting_a_student_reuses_their_details(self):
        """A returning student should be a confirmation, not a retype."""
        self._new_student(semester="1")
        form = Form(self.Student)
        form.id_number = "TEST-2026-00431"
        self.assertEqual(form.name, "Maria Santos")
        self.assertEqual(form.course_id, self.course_bsit)
        self.assertEqual(form.year_level, "2")

    def test_an_unknown_id_number_fills_in_nothing(self):
        """The shortcut must not invent details for a first-time student."""
        form = Form(self.Student)
        form.id_number = "TEST-NEVER-SEEN"
        self.assertFalse(form.name)

    def test_correcting_the_semester_reissues_the_enrollment_number(self):
        """An ID reading 1ST on a 2nd-semester admission is simply wrong."""
        student = self._new_student(semester="1")
        student.write({"semester": "2"})
        self.assertTrue(student.enrollment_number.startswith("ENR/2026-2027/2ND/"))

    def test_correcting_the_academic_year_reissues_the_enrollment_number(self):
        """Same reasoning as the semester: the number states the year."""
        student = self._new_student(school_year="2026-2027")
        student.write({"school_year": "2027-2028"})
        self.assertTrue(student.enrollment_number.startswith("ENR/2027-2028/1ST/"))

    def test_an_unrelated_edit_keeps_the_enrollment_number(self):
        """Reissuing on every write would make the number meaningless."""
        student = self._new_student()
        issued = student.enrollment_number
        student.write({"name": "Maria Santos-Cruz"})
        self.assertEqual(student.enrollment_number, issued)

    def test_this_years_admission_is_flagged_current(self):
        """The filter is only as good as the flag it searches on."""
        student = self._new_student(school_year=self.Student._default_school_year())
        self.assertTrue(student.is_current_year)

    def test_an_older_admission_is_not_flagged_current(self):
        """A filter that matches every year filters nothing."""
        self.assertFalse(self._new_student(school_year="2019-2020").is_current_year)

    def test_searching_current_year_returns_only_this_years_admissions(self):
        """This is what the search-view filter actually runs."""
        current = self._new_student(school_year=self.Student._default_school_year())
        old = self._new_student(school_year="2019-2020")
        found = self.Student.search([("is_current_year", "=", True)])
        self.assertIn(current, found)
        self.assertNotIn(old, found)

    def test_searching_not_current_year_returns_the_rest(self):
        """A negated filter must not quietly return everything."""
        current = self._new_student(school_year=self.Student._default_school_year())
        old = self._new_student(school_year="2019-2020")
        found = self.Student.search([("is_current_year", "=", False)])
        self.assertIn(old, found)
        self.assertNotIn(current, found)
