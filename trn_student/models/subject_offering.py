from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .academic_term import (
    SEMESTER_SELECTION,
    SEMESTER_SHORT,
    check_school_year,
    default_school_year,
    term_label,
)


class SubjectOffering(models.Model):
    """One subject as taught in one term by one professor.

    The catalogue entry (trn.subject) is timeless; this is where a subject
    meets a calendar and a teacher. Students enrol in an offering rather than
    in a subject, which is what keeps a 1st-semester grade separate from a
    2nd-semester retake of the same subject.
    """

    _name = "trn.subject.offering"
    _description = "Subject Offering"
    _order = "school_year desc, semester, id"
    _rec_names_search = ["subject_id.code", "subject_id.name"]

    subject_id = fields.Many2one(
        comodel_name="trn.subject",
        string="Subject",
        required=True,
        index=True,
        ondelete="restrict",
        help="Subject being offered",
    )
    school_year = fields.Char(
        string="Academic Year",
        required=True,
        default=lambda self: default_school_year(self),
        help="Academic year this offering runs in, as 'YYYY-YYYY'",
    )
    semester = fields.Selection(
        selection=SEMESTER_SELECTION,
        string="Semester",
        required=True,
        default="1",
        help="Term this offering runs in",
    )
    faculty_id = fields.Many2one(
        comodel_name="trn.faculty",
        string="Professor",
        ondelete="restrict",
        help="Professor teaching this offering. Optional: an offering may be " "published before it is staffed.",
    )
    grade_ids = fields.One2many(
        comodel_name="trn.grade",
        inverse_name="offering_id",
        string="Class List",
        help="Students taking this offering, and their grades",
    )
    student_count = fields.Integer(
        string="Student Count",
        compute="_compute_student_count",
        help="How many students are taking this offering",
    )
    active = fields.Boolean(
        default=True,
        help="Archive an offering that did not run instead of deleting it",
    )

    _unique_offering = models.Constraint(
        "UNIQUE(subject_id, school_year, semester)",
        "A subject can only be offered once per semester",
    )

    @api.depends("subject_id", "semester", "school_year")
    def _compute_display_name(self):
        """Show 'IT101 — Programming 1 (1st Sem 2026-2027)'."""
        for offering in self:
            term = SEMESTER_SHORT.get(offering.semester, "")
            offering.display_name = f"{offering.subject_id.display_name} ({term} {offering.school_year})"

    @api.depends("grade_ids")
    def _compute_student_count(self):
        """Count enrolled students so the list view can show class size."""
        for offering in self:
            offering.student_count = len(offering.grade_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Check the subject is not already offered this term before insert."""
        for vals in vals_list:
            filled = self._add_missing_default_values(vals)
            self._check_offering_available(filled.get("subject_id"), filled.get("school_year"), filled.get("semester"))
        return super().create(vals_list)

    def write(self, vals):
        """Re-check whenever any part of the offering key moves."""
        if {"subject_id", "school_year", "semester"} & set(vals):
            for offering in self:
                self._check_offering_available(
                    vals.get("subject_id", offering.subject_id.id),
                    vals.get("school_year", offering.school_year),
                    vals.get("semester", offering.semester),
                    exclude=offering,
                )
        return super().write(vals)

    @api.model
    def _check_offering_available(self, subject_id, school_year, semester, exclude=None):
        """Raise if this subject already runs in this term.

        Before the insert, not as a constrains: the SQL unique constraint
        would otherwise speak first and hand the user a Postgres error.
        """
        if not subject_id:
            return
        domain = [
            ("subject_id", "=", subject_id),
            ("school_year", "=", school_year),
            ("semester", "=", semester),
        ]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        duplicate = self.with_context(active_test=False).search(domain, limit=1)
        if duplicate:
            raise ValidationError(
                _(
                    "%(subject)s is already offered in %(term)s. Add students to "
                    "that offering rather than creating a second one.",
                    subject=duplicate.subject_id.display_name,
                    term=term_label(semester, school_year),
                )
            )

    @api.constrains("school_year")
    def _check_school_year(self):
        """An academic year must be two consecutive four-digit years."""
        for offering in self:
            check_school_year(offering.school_year)
