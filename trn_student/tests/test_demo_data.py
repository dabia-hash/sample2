from odoo.tests.common import TransactionCase


class TestStudentDemoData(TransactionCase):
    """The records in demo/ must be complete and consistent.

    Odoo 19 omits demo data from new databases unless --with-demo is passed, so
    these tests skip rather than fail on an ordinary test run. They earn their
    keep on a demo database, where a half-built record would otherwise only show
    up as a broken screen.
    """

    def _demo_students(self):
        """Return the demo students, or skip if demo data was not loaded."""
        students = self.env["trn.student"].search([("id_number", "like", "DEMO-%")])
        if not students:
            self.skipTest("Demo data not loaded (no --with-demo)")
        return students

    def test_demo_students_are_complete(self):
        """A demo student missing a course renders a broken form."""
        for student in self._demo_students():
            self.assertTrue(student.course_id, f"{student.id_number} has no course")
            self.assertTrue(student.year_level, f"{student.id_number} has no year level")
            self.assertTrue(student.name, f"{student.id_number} has no name")

    def test_demo_school_years_are_valid(self):
        """The constraint runs on create, but a later edit could slip past."""
        for student in self._demo_students():
            start, end = student.school_year.split("-")
            self.assertEqual(int(end), int(start) + 1, student.id_number)

    def test_demo_covers_more_than_one_course(self):
        """A demo with every student in one course shows nothing about grouping."""
        courses = self._demo_students().mapped("course_id")
        self.assertGreater(len(courses), 1)

    def test_demo_covers_more_than_one_year_level(self):
        """Same reasoning: the year filters need something to filter."""
        levels = set(self._demo_students().mapped("year_level"))
        self.assertGreater(len(levels), 1)

    def test_demo_students_carry_a_term(self):
        """A demo admission with no term cannot appear in the semester filters."""
        for student in self._demo_students():
            self.assertTrue(student.semester, f"{student.id_number} has no semester")
            self.assertTrue(student.enrollment_number, f"{student.id_number} has no enrollment number")

    def test_demo_covers_more_than_one_semester(self):
        """The point of the feature is a student appearing in two terms."""
        semesters = set(self._demo_students().mapped("semester"))
        self.assertGreater(len(semesters), 1)

    def test_demo_shows_a_student_admitted_twice(self):
        """One ID number across two terms is what the ledger shape is for."""
        students = self._demo_students()
        counts = {}
        for student in students:
            counts[student.id_number] = counts.get(student.id_number, 0) + 1
        self.assertTrue(
            any(count > 1 for count in counts.values()),
            "no demo student is admitted to more than one term",
        )

    def test_demo_courses_belong_to_a_department(self):
        """A course with no department breaks the Departments grouping."""
        courses = self._demo_students().mapped("course_id")
        for course in courses:
            self.assertTrue(course.department_id, f"{course.code} has no department")

    def test_demo_covers_more_than_one_department(self):
        """A demo with one department shows nothing about the grouping."""
        departments = self._demo_students().mapped("course_id.department_id")
        self.assertGreater(len(departments), 1)

    def _demo_grades(self):
        """Return the demo grade rows, or skip if demo data was not loaded."""
        grades = self.env["trn.grade"].search([("student_id", "in", self._demo_students().ids)])
        if not grades:
            self.skipTest("Demo data not loaded (no --with-demo)")
        return grades

    def test_demo_offerings_carry_a_term_and_a_subject(self):
        """An offering missing either cannot be matched to an admission."""
        for offering in self._demo_grades().mapped("offering_id"):
            self.assertTrue(offering.subject_id, "offering has no subject")
            self.assertTrue(offering.school_year, "offering has no academic year")
            self.assertTrue(offering.semester, "offering has no semester")

    def test_demo_offerings_match_their_students_term(self):
        """The rule the model enforces should hold in the shipped data too."""
        for grade in self._demo_grades():
            self.assertEqual(grade.offering_id.school_year, grade.student_id.school_year)
            self.assertEqual(grade.offering_id.semester, grade.student_id.semester)

    def test_demo_shows_a_graded_and_an_ungraded_row(self):
        """Both states have to be visible or the screen looks half-built."""
        grades = self._demo_grades()
        self.assertTrue(any(grade.grade for grade in grades), "no demo row is graded")
        self.assertTrue(any(not grade.grade for grade in grades), "no demo row is ungraded")

    def test_demo_shows_a_student_taking_several_subjects(self):
        """A one-subject demo shows nothing about the many-to-many."""
        counts = {}
        for grade in self._demo_grades():
            counts[grade.student_id.id] = counts.get(grade.student_id.id, 0) + 1
        self.assertTrue(any(count > 1 for count in counts.values()))

    def test_demo_offerings_have_a_professor(self):
        """Faculty assignment is the feature; the demo should show it."""
        for offering in self._demo_grades().mapped("offering_id"):
            self.assertTrue(offering.faculty_id, f"{offering.display_name} has no professor")
