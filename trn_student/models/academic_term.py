"""The academic term vocabulary, shared by everything that happens in one.

An admission, a subject offering and the grade joining them all sit in the
same term and all have to agree on what a term is. Keeping the selection,
the short forms and the "YYYY-YYYY" rule here means the three models cannot
drift apart, and a new model that happens in a term has one place to import
from.
"""

import re

from odoo import _, fields
from odoo.exceptions import ValidationError

SEMESTER_SELECTION = [
    ("1", "1st Semester"),
    ("2", "2nd Semester"),
    ("S", "Summer"),
]

# Segment used in the enrollment number, and the short form shown in
# display_name. The selection label itself is too long for a dropdown.
SEMESTER_CODES = {"1": "1ST", "2": "2ND", "S": "SUM"}
SEMESTER_SHORT = {"1": "1st Sem", "2": "2nd Sem", "S": "Summer"}

SCHOOL_YEAR_PATTERN = re.compile(r"^(\d{4})-(\d{4})$")


def default_school_year(record):
    """Offer the academic year starting this calendar year."""
    this_year = fields.Date.context_today(record).year
    return f"{this_year}-{this_year + 1}"


def check_school_year(value):
    """Raise unless the value is two consecutive four-digit years.

    Takes a plain string rather than a recordset so that every model with a
    school_year can call it from its own constrains without inheriting.
    """
    match = SCHOOL_YEAR_PATTERN.match(value or "")
    if not match:
        raise ValidationError(
            _(
                "Academic year '%(value)s' must look like '2026-2027'.",
                value=value,
            )
        )
    start, end = int(match.group(1)), int(match.group(2))
    if end != start + 1:
        raise ValidationError(
            _(
                "Academic year '%(value)s' must span two consecutive years, so '%(start)s-%(expected)s'.",
                value=value,
                start=start,
                expected=start + 1,
            )
        )


def term_label(semester, school_year):
    """Render a term the way a registrar says it, e.g. '1st Semester 2026-2027'."""
    return f"{dict(SEMESTER_SELECTION).get(semester, '')} {school_year}"
