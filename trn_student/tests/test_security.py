from odoo.exceptions import AccessError

from .common import StudentCase


class TestStudentSecurity(StudentCase):
    """Who may read, edit, and delete student and course records."""

    def test_registrar_can_create_a_student(self):
        """Enrolling students is the registrar's whole job."""
        student = self.Student.with_user(self.user_registrar).create(
            {
                "id_number": "TEST-2026-00500",
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
        self.assertEqual(course.name, self.course_bsit.name)

    def test_registrar_cannot_create_a_course(self):
        """The course list is configuration, not day-to-day data entry."""
        with self.assertRaises(AccessError):
            self.Course.with_user(self.user_registrar).create({"code": "TEST-SNEAK", "name": "Unauthorised Course"})

    def test_registrar_can_read_departments(self):
        """The course they pick shows its department; reading it must not fail."""
        department = self.Department.with_user(self.user_registrar).browse(self.department_ccs.id)
        self.assertEqual(department.name, self.department_ccs.name)

    def test_registrar_cannot_create_a_department(self):
        """Departments are configuration, like the course list."""
        with self.assertRaises(AccessError):
            self.Department.with_user(self.user_registrar).create(
                {"code": "TEST-SNEAK-DEPT", "name": "Unauthorised Department"}
            )

    def test_manager_can_create_a_department(self):
        """Maintaining the department list belongs with the course list."""
        department = self.Department.with_user(self.user_manager).create(
            {"code": "TEST-CBA", "name": "Test College of Business Administration"}
        )
        self.assertTrue(department.exists())

    def test_registrar_can_admit_a_returning_student(self):
        """Re-enrolling an existing student each term is routine registrar work."""
        self._new_student(semester="1")
        readmission = self.Student.with_user(self.user_registrar).create(
            {
                "id_number": "TEST-2026-00431",
                "name": "Maria Santos",
                "course_id": self.course_bsit.id,
                "year_level": "2",
                "school_year": "2026-2027",
                "semester": "2",
            }
        )
        self.assertTrue(readmission.enrollment_number)

    def test_registrar_can_read_subjects_and_faculty(self):
        """They must pick both when enrolling a student in a class."""
        subject = self.Subject.with_user(self.user_registrar).browse(self.subject_it101.id)
        faculty = self.Faculty.with_user(self.user_registrar).browse(self.faculty_reyes.id)
        self.assertEqual(subject.name, self.subject_it101.name)
        self.assertEqual(faculty.name, self.faculty_reyes.name)

    def test_registrar_cannot_maintain_the_subject_catalogue(self):
        """Subjects are configuration, like courses and departments."""
        with self.assertRaises(AccessError):
            self.Subject.with_user(self.user_registrar).create(
                {"code": "TEST-SNEAK-SUBJ", "name": "Unauthorised Subject"}
            )

    def test_registrar_cannot_create_an_offering(self):
        """Deciding what runs this term is not the registrar's call."""
        with self.assertRaises(AccessError):
            self.Offering.with_user(self.user_registrar).create(
                {
                    "subject_id": self.subject_it101.id,
                    "school_year": "2026-2027",
                    "semester": "S",
                }
            )

    def test_registrar_can_enrol_a_student_in_a_subject(self):
        """Enrolling students in classes is the registrar's day job."""
        student = self._new_student()
        grade = self.Grade.with_user(self.user_registrar).create(
            {"student_id": student.id, "offering_id": self.offering_it101.id}
        )
        self.assertTrue(grade.exists())

    def test_registrar_can_record_a_mark(self):
        """So is writing down the mark at the end of the term."""
        grade = self._new_grade(student=self._new_student())
        grade.with_user(self.user_registrar).write({"grade": "2.00"})
        self.assertEqual(grade.grade, "2.00")

    def test_registrar_cannot_delete_a_grade(self):
        """Deleting a mark loses history; correcting it is the supported route."""
        grade = self._new_grade(student=self._new_student())
        with self.assertRaises(AccessError):
            grade.with_user(self.user_registrar).unlink()

    def test_manager_can_maintain_the_catalogue_and_offerings(self):
        """Maintaining what is taught is what separates the two roles."""
        subject = self.Subject.with_user(self.user_manager).create(
            {"code": "TEST-MGR-SUBJ", "name": "Test Manager Subject"}
        )
        offering = self.Offering.with_user(self.user_manager).create(
            {"subject_id": subject.id, "school_year": "2026-2027", "semester": "1"}
        )
        self.assertTrue(offering.exists())

    def test_manager_can_delete_a_student(self):
        """Someone has to be able to remove a record created in error."""
        student = self._new_student()
        student.with_user(self.user_manager).unlink()
        self.assertFalse(student.exists())

    def test_manager_can_create_a_course(self):
        """Managing the course list is what separates the two roles."""
        course = self.Course.with_user(self.user_manager).create(
            {
                "code": "TEST-BSED",
                "name": "Test BS Education",
                "department_id": self.department_ccs.id,
            }
        )
        self.assertTrue(course.exists())

    def test_suite_administrator_inherits_manager_rights(self):
        """Granting Administration once must carry this module's manager rights.

        trn_security.group_trn_admin is linked to group_student_manager from this
        module's security_groups.xml; without that link an administrator would
        have to be given every module's manager group by hand.
        """
        admin_group = self.env.ref("trn_security.group_trn_admin")
        self.assertIn(self.group_manager, admin_group.implied_ids)

    def test_manager_inherits_registrar_rights(self):
        """A manager should never have to switch roles to enrol a student.

        group_ids holds only explicitly assigned groups in Odoo 19; the implied
        ones land in all_group_ids, which is what "inherits" means here.
        """
        self.assertIn(self.group_registrar, self.user_manager.all_group_ids)
