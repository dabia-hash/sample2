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
