from odoo.exceptions import UserError, ValidationError

from .common import ServiceRequestCase


class TestServiceRequestLifecycle(ServiceRequestCase):
    """The New -> Assigned -> In Progress -> Resolved -> Closed flow."""

    def test_new_request_starts_in_the_new_state(self):
        """A freshly submitted request is waiting for triage."""
        request = self._new_request()
        self.assertEqual(request.state, "new")

    def test_new_request_is_numbered_from_a_sequence(self):
        """Requests get a human-quotable reference, not a bare database id."""
        request = self._new_request()
        self.assertTrue(request.name.startswith("SR/"))

    def test_two_requests_get_different_references(self):
        """The sequence must not hand out the same number twice."""
        first = self._new_request()
        second = self._new_request()
        self.assertNotEqual(first.name, second.name)

    def test_submitted_date_is_stamped_on_creation(self):
        """Reporting on age needs a submission timestamp."""
        request = self._new_request()
        self.assertTrue(request.submitted_date)

    def test_office_defaults_to_the_requester_office(self):
        """The requester should not have to restate where they work."""
        request = self._new_request()
        self.assertEqual(request.office_id, self.office_head_quarters)

    def test_assigning_moves_the_request_to_assigned(self):
        """Naming an owner takes the request out of the triage queue."""
        request = self._new_request()
        request.assigned_user_id = self.user_officer
        request.action_assign()
        self.assertEqual(request.state, "assigned")

    def test_assigning_stamps_the_assignment_date(self):
        """Time-to-assign reporting needs the moment of assignment."""
        request = self._new_request()
        request.assigned_user_id = self.user_officer
        request.action_assign()
        self.assertTrue(request.assigned_date)

    def test_assigning_without_an_owner_is_rejected(self):
        """A request cannot be 'assigned' to nobody."""
        request = self._new_request()
        with self.assertRaises(UserError):
            request.action_assign()

    def test_assignee_must_belong_to_the_handling_team(self):
        """Work cannot be pushed onto someone outside the team."""
        request = self._new_request()
        with self.assertRaises(ValidationError):
            request.assigned_user_id = self.user_colleague

    def test_starting_work_moves_the_request_to_in_progress(self):
        """The requester can see that someone has actually begun."""
        request = self._new_request()
        request.assigned_user_id = self.user_officer
        request.action_assign()
        request.action_start()
        self.assertEqual(request.state, "in_progress")

    def test_work_cannot_start_before_assignment(self):
        """Skipping triage would hide unassigned work."""
        request = self._new_request()
        with self.assertRaises(UserError):
            request.action_start()

    def test_resolving_requires_a_resolution_note(self):
        """Closing the loop without saying what was done is not allowed."""
        request = self._new_request()
        request.assigned_user_id = self.user_officer
        request.action_assign()
        request.action_start()
        with self.assertRaises(UserError):
            request.action_resolve()

    def test_resolving_with_a_note_moves_to_resolved(self):
        """A resolution note is what makes the request resolvable."""
        request = self._new_request()
        request.assigned_user_id = self.user_officer
        request.action_assign()
        request.action_start()
        request.resolution = "Password reset and account unlocked."
        request.action_resolve()
        self.assertEqual(request.state, "resolved")
        self.assertTrue(request.resolved_date)

    def test_closing_a_resolved_request_moves_it_to_closed(self):
        """Closure is the terminal state of a successful request."""
        request = self._resolved_request()
        request.action_close()
        self.assertEqual(request.state, "closed")
        self.assertTrue(request.closed_date)

    def test_an_unresolved_request_cannot_be_closed(self):
        """Closing must not be a shortcut around doing the work."""
        request = self._new_request()
        with self.assertRaises(UserError):
            request.action_close()

    def test_a_request_can_be_cancelled_before_closure(self):
        """Requests raised in error are cancelled, not deleted."""
        request = self._new_request()
        request.action_cancel()
        self.assertEqual(request.state, "cancelled")

    def test_a_closed_request_cannot_be_cancelled(self):
        """Completed history must stay intact."""
        request = self._resolved_request()
        request.action_close()
        with self.assertRaises(UserError):
            request.action_cancel()

    def _resolved_request(self):
        """Drive a request all the way to Resolved."""
        request = self._new_request()
        request.assigned_user_id = self.user_officer
        request.action_assign()
        request.action_start()
        request.resolution = "Password reset and account unlocked."
        request.action_resolve()
        return request
