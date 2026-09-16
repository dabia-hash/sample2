"""Give existing student rows a term before the columns turn NOT NULL.

Runs before the models are loaded, so it works in plain SQL on the old
table. Every row that predates this version becomes a 1st-semester
admission of the academic year it already carries — which is what those
rows always meant.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        ALTER TABLE trn_student
            ADD COLUMN IF NOT EXISTS semester VARCHAR,
            ADD COLUMN IF NOT EXISTS enrollment_number VARCHAR
        """
    )
    cr.execute("UPDATE trn_student SET semester = '1' WHERE semester IS NULL")
    backfilled = cr.rowcount

    # The ID number alone is no longer unique; the admission triple is.
    # Dropping it here keeps the ORM from tripping over pre-existing rows.
    cr.execute("ALTER TABLE trn_student DROP CONSTRAINT IF EXISTS trn_student_unique_id_number")

    _logger.info("trn_student: %s row(s) marked as 1st-semester admissions", backfilled)
