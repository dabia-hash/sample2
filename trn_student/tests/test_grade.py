from psycopg2.errors import RestrictViolation

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import StudentCase


class TestGrade(StudentCase):
    """The junction: one admission takes one offering, and earns a mark."""

    def test_a_student_can_be_enrolled_in_a_subject(self):
        """The happy path, and the row that exists before any mark is given."""
        student = self._new_student()
        grade = self._new_grade(student=student)
        self.assertEqual(grade.student_id, student)
        self.assertEqual(grade.offering_id, self.offering_it101)
        self.assertFalse(grade.grade)

    def test_one_student_can_take_many_subjects(self):
        """Half of the many-to-many."""
        student = self._new_student()
        other = self._new_offering(subject_id=self._new_subject("TEST-MATH1").id)
        self._new_grade(student=student)
        self._new_grade(student=student, offering=other)
        self.assertEqual(len(student.grade_ids), 2)

    def test_one_subject_can_have_many_students(self):
        """The other half, and the offering's class list."""
        first = self._new_student(id_number="TEST-M2M-1")
        second = self._new_student(id_number="TEST-M2M-2")
        self._new_grade(student=first)
        self._new_grade(student=second)
        self.offering_it101.invalidate_recordset(["grade_ids", "student_count"])
        self.assertEqual(self.offering_it101.student_count, 2)

    def test_the_same_subject_cannot_be_added_twice(self):
        """One admission takes one offering once."""
        student = self._new_student()
        self._new_grade(student=student)
        with self.assertRaises(ValidationError):
            self._new_grade(student=student)

    def test_an_offering_from_another_semester_is_rejected(self):
        """A 1st-semester admission cannot take a 2nd-semester offering."""
        student = self._new_student(semester="1")
        other_term = self._new_offering(semester="2")
        with self.assertRaises(ValidationError):
            self._new_grade(student=student, offering=other_term)

    def test_an_offering_from_another_year_is_rejected(self):
        """Same rule across academic years."""
        student = self._new_student(school_year="2026-2027")
        next_year = self._new_offering(school_year="2027-2028")
        with self.assertRaises(ValidationError):
            self._new_grade(student=student, offering=next_year)

    def test_the_rejection_names_both_terms(self):
        """'Invalid' tells a registrar nothing; the two terms do."""
        student = self._new_student(semester="1")
        other_term = self._new_offering(semester="2")
        with self.assertRaises(ValidationError) as caught:
            self._new_grade(student=student, offering=other_term)
        message = str(caught.exception)
        self.assertIn("2nd Semester 2026-2027", message)
        self.assertIn("1st Semester 2026-2027", message)

    def test_a_matching_term_is_accepted(self):
        """The rule must not reject the ordinary case."""
        student = self._new_student(semester="2")
        same_term = self._new_offering(semester="2")
        grade = self._new_grade(student=student, offering=same_term)
        self.assertTrue(grade.exists())

    def test_a_grade_can_be_recorded(self):
        """The point of the row, once the term ends."""
        grade = self._new_grade(student=self._new_student())
        grade.grade = "1.75"
        self.assertEqual(grade.grade, "1.75")

    def test_a_passing_mark_is_flagged_passing(self):
        """3.00 is the passing boundary, not a failure."""
        grade = self._new_grade(student=self._new_student(), grade="3.00")
        self.assertTrue(grade.is_passing)

    def test_a_failing_mark_is_not_flagged_passing(self):
        """5.00 is the only numeric failure on this scale."""
        grade = self._new_grade(student=self._new_student(), grade="5.00")
        self.assertFalse(grade.is_passing)

    def test_an_ungraded_row_is_not_flagged_passing(self):
        """Blank means not yet graded, which is not the same as passing."""
        self.assertFalse(self._new_grade(student=self._new_student()).is_passing)

    def test_an_incomplete_is_not_flagged_passing(self):
        """INC is unfinished work, not a pass."""
        grade = self._new_grade(student=self._new_student(), grade="INC")
        self.assertFalse(grade.is_passing)

    def test_the_subject_and_professor_are_reachable_from_the_grade(self):
        """The student's table shows them without hopping through the offering."""
        grade = self._new_grade(student=self._new_student())
        self.assertEqual(grade.subject_id, self.subject_it101)
        self.assertEqual(grade.faculty_id, self.faculty_reyes)
        self.assertEqual(grade.units, 3.0)

    def test_deleting_an_admission_takes_its_grades_with_it(self):
        """A grade row has no meaning without the admission it belongs to."""
        student = self._new_student()
        grade = self._new_grade(student=student)
        student.unlink()
        self.assertFalse(grade.exists())

    @mute_logger("odoo.sql_db")
    def test_an_offering_with_a_class_list_cannot_be_deleted(self):
        """Deleting it would erase marks that students earned."""
        self._new_grade(student=self._new_student())
        with self.assertRaises(RestrictViolation):
            self.offering_it101.unlink()

    def test_the_class_list_can_show_who_the_student_is(self):
        """A class list of bare names cannot be reconciled with the registry."""
        student = self._new_student()
        grade = self._new_grade(student=student)
        self.assertEqual(grade.enrollment_number, student.enrollment_number)
        self.assertEqual(grade.course_id, student.course_id)
        self.assertEqual(grade.id_number, student.id_number)
