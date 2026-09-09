from datetime import timedelta

from odoo import fields

from .common import ServiceRequestCase


class TestServiceRequestDeadline(ServiceRequestCase):
    """Target resolution deadlines and the overdue flag."""

    def test_deadline_is_the_target_hours_after_submission(self):
        """The catalogue's target resolution time defines the deadline."""
        request = self._new_request()
        expected = request.submitted_date + timedelta(hours=4)
        self.assertEqual(request.deadline_date, expected)

    def test_deadline_follows_a_change_of_service(self):
        """Re-classifying a request must not leave the old deadline behind."""
        urgent = self.Catalog.create(
            {"name": "Network Failure", "code": "TEST_NETWORK_FAILURE", "target_resolution_hours": 1}
        )
        request = self._new_request()
        request.catalog_id = urgent
        self.assertEqual(request.deadline_date, request.submitted_date + timedelta(hours=1))

    def test_a_request_inside_its_deadline_is_not_overdue(self):
        """Nothing is late until the deadline actually passes."""
        request = self._new_request()
        self.assertFalse(request.is_overdue)

    def test_an_open_request_past_its_deadline_is_overdue(self):
        """Breaching the target must be visible without running a report."""
        request = self._new_request()
        request.submitted_date = fields.Datetime.now() - timedelta(hours=10)
        self.assertTrue(request.is_overdue)

    def test_a_resolved_request_is_never_overdue(self):
        """Overdue means 'still owed work', not 'took a long time'."""
        request = self._new_request()
        request.submitted_date = fields.Datetime.now() - timedelta(hours=10)
        request.assigned_user_id = self.user_officer
        request.action_assign()
        request.action_start()
        request.resolution = "Reset done."
        request.action_resolve()
        self.assertFalse(request.is_overdue)

    def test_a_cancelled_request_is_never_overdue(self):
        """Cancelled work is not owed either."""
        request = self._new_request()
        request.submitted_date = fields.Datetime.now() - timedelta(hours=10)
        request.action_cancel()
        self.assertFalse(request.is_overdue)

    def test_overdue_requests_can_be_filtered_in_a_search(self):
        """The 'Overdue' filter in the search view must actually work."""
        late = self._new_request()
        late.submitted_date = fields.Datetime.now() - timedelta(hours=10)
        on_time = self._new_request()

        overdue = self.Request.search([("is_overdue", "=", True)])

        self.assertIn(late, overdue)
        self.assertNotIn(on_time, overdue)
