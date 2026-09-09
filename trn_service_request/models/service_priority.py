"""Shared vocabulary URIs and selections for the service request domain.

Priority is a static Selection because it drives Odoo's star widget and the
ordering of the queue, both of which require a Selection field. The matching
vocabulary code is derived from it for reporting - see
`trn.service.request.priority_code_id`.
"""

PRIORITY_VOCABULARY_URI = "urn:trn:vocab:service-priority"
CATEGORY_VOCABULARY_URI = "urn:trn:vocab:service-category"

PRIORITY_SELECTION = [
    ("low", "Low"),
    ("normal", "Normal"),
    ("high", "High"),
    ("urgent", "Urgent"),
]

RATING_SELECTION = [
    ("1", "Very dissatisfied"),
    ("2", "Dissatisfied"),
    ("3", "Neutral"),
    ("4", "Satisfied"),
    ("5", "Very satisfied"),
]

#: States in which IT still owes the requester work.
OPEN_STATES = ["new", "assigned", "in_progress"]
