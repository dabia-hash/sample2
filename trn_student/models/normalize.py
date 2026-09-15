"""Shared normalisation for the identifying codes on both models.

A course code and a student ID number are both typed by hand and both have to
compare equal regardless of how they were typed, so they normalise the same way
in one place rather than twice.
"""


def normalize_code(value):
    """Strip, collapse internal whitespace, and uppercase an identifying code.

    Returns an empty string for a missing or blank value, so callers can treat
    "absent" and "whitespace only" identically.
    """
    if not value:
        return ""
    return " ".join(value.split()).upper()
