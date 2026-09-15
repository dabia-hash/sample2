from odoo.exceptions import AccessError

from .common import StudentCase


class TestStudentSecurity(StudentCase):
    """Who may read, edit, and delete student and course records."""

    def test_registrar_can_create_a_student(self):
        """Enrolling students is the registrar's whole job."""
        student = self.Student.with_user(self.user_registrar).create(
            {
                "id_number": "2026-00500",
                "name": "Registrar Created",
                "course_id": self.course_bsit.id,
                "year_level": "1",
                "school_year": "2026-2027",
            }
        )
        self.assertTrue(student.exists())

    def test_registrar_can_edit_a_student(self):
        """Correcting a misspelled name must not need a manager."""
        student = self._new_student()
        student.with_user(self.user_registrar).write({"name": "Maria S. Santos"})
        self.assertEqual(student.name, "Maria S. Santos")

    def test_registrar_cannot_delete_a_student(self):
        """Deletion loses history; archiving is the supported route."""
        student = self._new_student()
        with self.assertRaises(AccessError):
            student.with_user(self.user_registrar).unlink()

    def test_registrar_can_read_courses(self):
        """They must pick a course when enrolling someone."""
        course = self.Course.with_user(self.user_registrar).browse(self.course_bsit.id)
        self.assertEqual(course.name, "BS Information Technology")

    def test_registrar_cannot_create_a_course(self):
        """The course list is configuration, not day-to-day data entry."""
        with self.assertRaises(AccessError):
            self.Course.with_user(self.user_registrar).create({"code": "SNEAK", "name": "Unauthorised Course"})

    def test_manager_can_delete_a_student(self):
        """Someone has to be able to remove a record created in error."""
        student = self._new_student()
        student.with_user(self.user_manager).unlink()
        self.assertFalse(student.exists())

    def test_manager_can_create_a_course(self):
        """Managing the course list is what separates the two roles."""
        course = self.Course.with_user(self.user_manager).create({"code": "BSED", "name": "BS Education"})
        self.assertTrue(course.exists())

    def test_manager_inherits_registrar_rights(self):
        """A manager should never have to switch roles to enrol a student.

        group_ids holds only explicitly assigned groups in Odoo 19; the implied
        ones land in all_group_ids, which is what "inherits" means here.
        """
        self.assertIn(self.group_registrar, self.user_manager.all_group_ids)
