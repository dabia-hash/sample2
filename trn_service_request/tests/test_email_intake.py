from odoo.exceptions import ValidationError

from .common import ServiceRequestCase

MAIL_TEMPLATE = """Return-Path: <{email_from}>
To: {to}
From: {email_from}
Subject: {subject}
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 7bit
Message-ID: {msg_id}
Date: Tue, 09 Sep 2026 09:00:00 +0000
{extra}
{body}
"""


class TestServiceRequestEmailIntake(ServiceRequestCase):
    """Requests raised by emailing a team's address.

    Only known internal users may open a request by email; anything else is
    refused so that the queue cannot be filled by an outsider.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alias_domain = cls.env["mail.alias.domain"].create(
            {"name": "example.com", "catchall_alias": "catchall-test"}
        )
        cls.user_requester.email = "ho.requester@example.com"
        cls.user_colleague.email = "ho.colleague@example.com"

        cls.team.write(
            {
                "default_catalog_id": cls.catalog_account_reset.id,
                "alias_domain_id": cls.alias_domain.id,
                "alias_name": "accounts",
            }
        )
        cls.team_address = f"accounts@{cls.alias_domain.name}"

    def _send(self, email_from, subject="Cannot log in", body="Locked out.", extra="", msg_id=None):
        """Push a raw email through the mail gateway, as the gateway would."""
        mail = MAIL_TEMPLATE.format(
            email_from=email_from,
            to=self.team_address,
            subject=subject,
            body=body,
            extra=extra,
            msg_id=msg_id or "<test-909-0001@example.com>",
        )
        return self.env["mail.thread"].sudo().message_process(None, mail)

    def _requests(self):
        """Every request currently visible, newest first."""
        return self.Request.search([])

    def test_email_from_a_known_user_creates_a_request(self):
        """Mailing the team address is a way to raise a request."""
        before = self._requests()
        self._send("ho.requester@example.com")
        created = self._requests() - before
        self.assertEqual(len(created), 1)

    def test_emailed_request_belongs_to_the_sender(self):
        """The sender becomes the requester, not some catch-all account."""
        before = self._requests()
        self._send("ho.requester@example.com")
        created = self._requests() - before
        self.assertEqual(created.requester_id, self.user_requester)

    def test_emailed_request_is_routed_to_the_addressed_team(self):
        """The address that was mailed decides which team handles it."""
        before = self._requests()
        self._send("ho.requester@example.com")
        created = self._requests() - before
        self.assertEqual(created.team_id, self.team)

    def test_emailed_request_takes_the_team_default_service(self):
        """catalog_id is required, so the team's default service supplies it."""
        before = self._requests()
        self._send("ho.requester@example.com")
        created = self._requests() - before
        self.assertEqual(created.catalog_id, self.catalog_account_reset)

    def test_email_subject_becomes_the_request_title(self):
        """The subject is the one-line summary IT triages from."""
        before = self._requests()
        self._send("ho.requester@example.com", subject="Printer on fire")
        created = self._requests() - before
        self.assertEqual(created.title, "Printer on fire")

    def test_email_without_a_subject_still_creates_a_request(self):
        """title is required, so an empty subject must not lose the request."""
        before = self._requests()
        self._send("ho.requester@example.com", subject="")
        created = self._requests() - before
        self.assertEqual(len(created), 1)
        self.assertTrue(created.title)

    def test_emailed_request_is_numbered_from_the_sequence(self):
        """Odoo's message_new copies the subject into _rec_name by default.

        On this model _rec_name is the sequence reference, so without an
        explicit override an emailed request is 'named' after its subject and
        loses its SR/ number entirely.
        """
        before = self._requests()
        self._send("ho.requester@example.com", subject="Laptop will not boot")
        created = self._requests() - before
        self.assertTrue(
            created.name.startswith("SR/"),
            f"emailed request took the subject as its reference: {created.name!r}",
        )

    def test_emailed_request_takes_the_office_of_the_sender(self):
        """Office-head visibility must work for emailed requests too."""
        before = self._requests()
        self._send("ho.requester@example.com")
        created = self._requests() - before
        self.assertEqual(created.office_id, self.office_head_quarters)

    def test_email_from_an_unknown_sender_creates_no_request(self):
        """An outsider must not be able to open tickets in the queue.

        The gateway bounces the mail rather than raising, so the contract
        under test is simply that nothing was created.
        """
        before = self._requests()
        self._send("stranger@elsewhere.example.com")
        self.assertFalse(self._requests() - before)

    def test_email_from_a_deactivated_user_creates_no_request(self):
        """Access ends when the account is archived, not when the mailbox dies."""
        self.user_colleague.active = False
        before = self._requests()
        self._send("ho.colleague@example.com")
        self.assertFalse(self._requests() - before)

    def test_reply_to_a_request_does_not_create_a_second_request(self):
        """A reply belongs on the existing thread, not in a new ticket."""
        before = self._requests()
        self._send("ho.requester@example.com", msg_id="<test-909-0002@example.com>")
        created = self._requests() - before
        self.assertEqual(len(created), 1)

        messages_before = len(created.message_ids)
        self._send(
            "ho.requester@example.com",
            subject="Re: Cannot log in",
            body="Still locked out, any update?",
            msg_id="<test-909-0003@example.com>",
            extra="In-Reply-To: <test-909-0002@example.com>\nReferences: <test-909-0002@example.com>",
        )

        self.assertEqual(len(self._requests() - before), 1, "reply opened a second request")
        self.assertGreater(len(created.message_ids), messages_before)

    def test_a_reply_cannot_change_the_request_state(self):
        """An inbound email must not be able to drive the workflow."""
        before = self._requests()
        self._send("ho.requester@example.com", msg_id="<test-909-0004@example.com>")
        created = self._requests() - before
        created.assigned_user_id = self.user_officer
        created.action_assign()

        self._send(
            "ho.requester@example.com",
            subject="Re: Cannot log in",
            body="Thanks!",
            msg_id="<test-909-0005@example.com>",
            extra="In-Reply-To: <test-909-0004@example.com>\nReferences: <test-909-0004@example.com>",
        )
        self.assertEqual(created.state, "assigned")


class TestServiceTeamAliasConfiguration(ServiceRequestCase):
    """Guard rails on configuring a team's email address."""

    def test_team_with_an_alias_must_have_a_default_service(self):
        """Otherwise inbound mail fails deep in the gateway on a required field."""
        domain = self.env["mail.alias.domain"].create({"name": "guard.example.com", "catchall_alias": "catchall-guard"})
        with self.assertRaises(ValidationError):
            self.Team.create(
                {
                    "name": "Network Team",
                    "code": "NET_GUARD",
                    "alias_domain_id": domain.id,
                    "alias_name": "network",
                }
            )

    def test_team_without_an_alias_needs_no_default_service(self):
        """Most teams never receive email and must stay simple to create."""
        team = self.Team.create({"name": "Desk Team", "code": "DESK"})
        self.assertFalse(team.alias_name)
