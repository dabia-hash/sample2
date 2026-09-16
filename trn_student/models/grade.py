from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .academic_term import term_label

# The Philippine scale, as fixed steps rather than a float: 1.60 is not a
# grade anyone can award, so it should not be typeable.
GRADE_SELECTION = [
    ("1.00", "1.00"),
    ("1.25", "1.25"),
    ("1.50", "1.50"),
    ("1.75", "1.75"),
    ("2.00", "2.00"),
    ("2.25", "2.25"),
    ("2.50", "2.50"),
    ("2.75", "2.75"),
    ("3.00", "3.00"),
    ("5.00", "5.00"),
    ("INC", "INC"),
    ("DRP", "DRP"),
]

# 3.00 is the passing boundary. 5.00 fails; INC and DRP are neither, and a
# blank grade means the term is not over yet.
PASSING_GRADES = {"1.00", "1.25", "1.50", "1.75", "2.00", "2.25", "2.50", "2.75", "3.00"}


class Grade(models.Model):
    """One student's enrolment in one subject offering, and the mark earned.

    Despite the name, a row exists from the moment a student is enrolled in
    the offering — well before anyone has a mark to record. A blank `grade`
    is the normal state for most of a semester and means "not yet graded",
    which is not the same as failing.

    This is the join that makes the relationship many-to-many in both
    directions: an admission has many of these rows, and so does an offering.
    """

    _name = "trn.grade"
    _description = "Subject Grade"
    _order = "student_id, subject_id"
    _rec_names_search = ["student_id.name", "subject_id.code"]

    student_id = fields.Many2one(
        comodel_name="trn.student",
        string="Student",
        required=True,
        index=True,
        ondelete="cascade",
        help="The admission this enrolment belongs to",
    )
    offering_id = fields.Many2one(
        comodel_name="trn.subject.offering",
        string="Offering",
        required=True,
        index=True,
        ondelete="restrict",
        help="Subject offering the student is taking",
    )
    grade = fields.Selection(
        selection=GRADE_SELECTION,
        string="Grade",
        help="Mark earned, on the 1.00-5.00 scale. Leave blank until the term ends.",
    )
    subject_id = fields.Many2one(
        related="offering_id.subject_id",
        string="Subject",
        store=True,
        index=True,
        help="Subject being taken, drawn from the offering",
    )
    faculty_id = fields.Many2one(
        related="offering_id.faculty_id",
        string="Professor",
        store=True,
        help="Professor teaching the offering",
    )
    units = fields.Float(
        related="offering_id.subject_id.units",
        string="Units",
        store=True,
        help="Credit units the subject carries",
    )
    school_year = fields.Char(
        related="offering_id.school_year",
        string="Academic Year",
        store=True,
        help="Academic year of the offering",
    )
    semester = fields.Selection(
        related="offering_id.semester",
        string="Semester",
        store=True,
        help="Term of the offering",
    )
    id_number = fields.Char(
        related="student_id.id_number",
        string="ID Number",
        help="The student's institutional number, shown on the class list",
    )
    enrollment_number = fields.Char(
        related="student_id.enrollment_number",
        string="Enrollment ID",
        help="Identifies the admission this enrolment belongs to",
    )
    course_id = fields.Many2one(
        related="student_id.course_id",
        string="Course",
        help="Course the student is enrolled in",
    )
    is_passing = fields.Boolean(
        string="Passing",
        compute="_compute_is_passing",
        store=True,
        help="Whether the mark earned is a passing one. Blank, INC and DRP are not.",
    )

    _unique_enrolment = models.Constraint(
        "UNIQUE(student_id, offering_id)",
        "A student takes a subject only once per term",
    )

    @api.depends("student_id", "subject_id")
    def _compute_display_name(self):
        """Show whose mark in which subject; either alone is ambiguous."""
        for record in self:
            record.display_name = f"{record.subject_id.code} — {record.student_id.name}"

    @api.depends("grade")
    def _compute_is_passing(self):
        """Blank is not yet graded, so it is not passing either."""
        for record in self:
            record.is_passing = record.grade in PASSING_GRADES

    @api.model_create_multi
    def create(self, vals_list):
        """Check the term matches and the subject is not doubled, before insert."""
        for vals in vals_list:
            filled = self._add_missing_default_values(vals)
            self._check_term_matches(filled.get("student_id"), filled.get("offering_id"))
            self._check_not_already_taken(filled.get("student_id"), filled.get("offering_id"))
        return super().create(vals_list)

    def write(self, vals):
        """Re-check whenever the admission or the offering moves."""
        if {"student_id", "offering_id"} & set(vals):
            for record in self:
                student_id = vals.get("student_id", record.student_id.id)
                offering_id = vals.get("offering_id", record.offering_id.id)
                self._check_term_matches(student_id, offering_id)
                self._check_not_already_taken(student_id, offering_id, exclude=record)
        return super().write(vals)

    @api.model
    def _check_term_matches(self, student_id, offering_id):
        """Raise unless the admission and the offering are in the same term.

        Before the insert rather than as a constrains, so the registrar gets
        a sentence naming both terms instead of a foreign-key error.
        """
        if not student_id or not offering_id:
            return
        student = self.env["trn.student"].browse(student_id)
        offering = self.env["trn.subject.offering"].browse(offering_id)
        if (student.school_year, student.semester) == (offering.school_year, offering.semester):
            return
        raise ValidationError(
            _(
                "%(subject)s is offered in %(offered)s, but this admission is for "
                "%(admitted)s. A student can only take subjects offered in their own term.",
                subject=offering.subject_id.display_name,
                offered=term_label(offering.semester, offering.school_year),
                admitted=term_label(student.semester, student.school_year),
            )
        )

    @api.model
    def _check_not_already_taken(self, student_id, offering_id, exclude=None):
        """Raise if this admission already takes this offering."""
        if not student_id or not offering_id:
            return
        domain = [("student_id", "=", student_id), ("offering_id", "=", offering_id)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        duplicate = self.search(domain, limit=1)
        if duplicate:
            raise ValidationError(
                _(
                    "%(student)s is already taking %(subject)s this term. "
                    "Edit the existing row rather than adding a second one.",
                    student=duplicate.student_id.name,
                    subject=duplicate.subject_id.display_name,
                )
            )
