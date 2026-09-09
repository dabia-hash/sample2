from odoo.exceptions import UserError

from .common import ServiceRequestCase


class TestServiceRequestRating(ServiceRequestCase):
    """Satisfaction rating left by the requester after closure."""

    def setUp(self):
        super().setUp()
        self.request = self._new_request()
        self.request.assigned_user_id = self.user_officer
        self.request.action_assign()
        self.request.action_start()
        self.request.resolution = "Password reset and account unlocked."
        self.request.action_resolve()

    def _rate(self, user, value="5", comment="Quick and helpful."):
        """Run the rating wizard as the given user."""
        wizard = (
            self.env["trn.service.request.rating.wizard"]
            .with_user(user)
            .with_context(active_model="trn.service.request", active_id=self.request.id)
            .create({"rating_value": value, "rating_comment": comment})
        )
        return wizard.action_submit_rating()

    def test_requester_can_rate_a_closed_request(self):
        """The person who raised the request judges whether it was fixed."""
        self.request.action_close()
        self._rate(self.user_requester)
        self.assertEqual(self.request.rating_value, "5")

    def test_rating_comment_is_stored(self):
        """Free-text feedback is kept alongside the score."""
        self.request.action_close()
        self._rate(self.user_requester, comment="Sorted within the hour.")
        self.assertEqual(self.request.rating_comment, "Sorted within the hour.")

    def test_a_request_cannot_be_rated_before_it_is_closed(self):
        """Rating measures the finished job, not work in flight."""
        with self.assertRaises(UserError):
            self._rate(self.user_requester)

    def test_only_the_requester_may_rate(self):
        """A colleague cannot score someone else's request."""
        self.request.action_close()
        with self.assertRaises(UserError):
            self._rate(self.user_colleague)

    def test_a_request_cannot_be_rated_twice(self):
        """The first verdict stands; re-rating would distort team averages."""
        self.request.action_close()
        self._rate(self.user_requester)
        with self.assertRaises(UserError):
            self._rate(self.user_requester, value="1")
