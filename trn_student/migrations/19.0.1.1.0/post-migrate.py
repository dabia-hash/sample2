"""File existing courses under a department, and number existing admissions.

Runs after the models are loaded, which is what both halves need: the
department model has to exist before a department can be created, and the
enrollment numbers have to come from the real sequence rather than from
hand-rolled SQL.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    _assign_courses_to_a_department(env, cr)
    _number_existing_admissions(env)


def _assign_courses_to_a_department(env, cr):
    """Courses predate departments, so park them under a real one."""
    orphans = env["trn.course"].with_context(active_test=False).search([("department_id", "=", False)])
    if orphans:
        department = env["trn.department"].with_context(active_test=False).search(
            [("code", "=", "GENERAL")], limit=1
        )
        if not department:
            department = env["trn.department"].create(
                {"code": "GENERAL", "name": "General"}
            )
        orphans.write({"department_id": department.id})
        _logger.info("trn_course: %s course(s) filed under %s", len(orphans), department.code)

    # The ALTER below is raw SQL, so it sees the table as Postgres has it, not
    # as the ORM intends it. Without this flush the writes above are still
    # pending in the cache and the constraint fails on rows it just fixed.
    env.flush_all()

    # The column could not be made NOT NULL while rows still had no
    # department; now that every row has one, enforce it.
    cr.execute("ALTER TABLE trn_course ALTER COLUMN department_id SET NOT NULL")


def _number_existing_admissions(env):
    """Draw a real sequence-backed number for every row that has none."""
    Student = env["trn.student"]
    unnumbered = Student.with_context(active_test=False).search([("enrollment_number", "=", False)])
    for student in unnumbered:
        student.enrollment_number = Student._next_enrollment_number(
            student.school_year, student.semester
        )
    if unnumbered:
        _logger.info("trn_student: numbered %s existing admission(s)", len(unnumbered))
