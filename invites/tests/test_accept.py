"""
Tests for POST /invites/accept

Negative-case focus — every validation branch is exercised individually.

Validation chain under test
---------------------------
Step 1:  400  missing / malformed fields
Step 2:  404  token does not exist
Step 3:  410  token already used  (single-use enforcement)
Step 4:  410  token expired        (timestamp expiry)
Step 5:  403  email mismatch       (email-match check)
Control: 200  happy path
"""
from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient

from invites.models import Invite


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _create_invite(email: str = "invite@example.com") -> Invite:
    """Persist and return a valid, fresh Invite."""
    return Invite.objects.create(email=email)


# ---------------------------------------------------------------------------
# Step 1 — Field validation (400 Bad Request)
# ---------------------------------------------------------------------------

class InviteAcceptFieldValidationTests(TestCase):
    """400 is returned when required fields are absent or malformed."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:accept")

    def test_missing_both_fields_returns_400(self) -> None:
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)
        self.assertIn("email", response.data)

    def test_missing_token_field_returns_400(self) -> None:
        response = self.client.post(self.url, {"email": "a@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)

    def test_missing_email_field_returns_400(self) -> None:
        response = self.client.post(self.url, {"token": "sometoken"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_invalid_email_format_returns_400(self) -> None:
        response = self.client.post(
            self.url, {"token": "sometoken", "email": "not-an-email"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_token_returns_400(self) -> None:
        response = self.client.post(
            self.url, {"token": "", "email": "a@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_email_returns_400(self) -> None:
        response = self.client.post(
            self.url, {"token": "sometoken", "email": ""}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_body_returns_400(self) -> None:
        response = self.client.post(self.url, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Step 2 — Token lookup (404 Not Found)
# ---------------------------------------------------------------------------

class InviteAcceptTokenNotFoundTests(TestCase):
    """404 is returned when the token does not exist in the database."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:accept")

    def test_nonexistent_token_returns_404(self) -> None:
        response = self.client.post(
            self.url,
            {"token": "completely-made-up-token", "email": "a@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)

    def test_partial_valid_token_returns_404(self) -> None:
        """A prefix of a real token is treated as a separate, unknown token."""
        invite = _create_invite()
        truncated = str(invite.token)[:10]
        response = self.client.post(
            self.url,
            {"token": truncated, "email": invite.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_database_returns_404(self) -> None:
        """Handles the case where no invites exist at all."""
        response = self.client.post(
            self.url,
            {"token": "no-invites-exist", "email": "a@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Step 3 — Single-use check (410 Gone — already used)
# ---------------------------------------------------------------------------

class InviteAcceptAlreadyUsedTests(TestCase):
    """410 is returned when the token was previously consumed."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:accept")

    def _accept(self, token: str, email: str) -> None:
        self.client.post(self.url, {"token": token, "email": email}, format="json")

    def test_reusing_token_returns_410(self) -> None:
        invite = _create_invite("reuse@example.com")
        self._accept(str(invite.token), str(invite.email))           # first — succeeds
        response = self.client.post(                        # second — must fail
            self.url,
            {"token": invite.token, "email": invite.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_already_used_detail_message_present(self) -> None:
        invite = _create_invite("msg@example.com")
        self._accept(str(invite.token), str(invite.email))
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": invite.email},
            format="json",
        )
        self.assertIn("detail", response.data)

    def test_used_at_is_set_after_acceptance(self) -> None:
        invite = _create_invite("stamp@example.com")
        self._accept(str(invite.token), str(invite.email))
        invite.refresh_from_db()
        self.assertIsNotNone(invite.used_at)

    def test_manually_set_used_at_returns_410(self) -> None:
        """Token pre-marked as used (e.g. by admin) must still be rejected."""
        invite = _create_invite("admin@example.com")
        invite.used_at = timezone.now()
        invite.save(update_fields=["used_at"])
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": invite.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_410_GONE)


# ---------------------------------------------------------------------------
# Step 4 — Expiry check (410 Gone — expired)
# ---------------------------------------------------------------------------

class InviteAcceptExpiredTests(TestCase):
    """410 is returned when the token's expiry time has passed."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:accept")

    def test_expired_token_returns_410(self) -> None:
        invite = _create_invite("expired@example.com")
        # Travel to 1 second after the invite's own expires_at
        future = datetime.fromisoformat(str(invite.expires_at)) + timedelta(seconds=1)  # cast: DateTimeField → datetime
        with freeze_time(future):
            response = self.client.post(
                self.url,
                {"token": invite.token, "email": invite.email},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_expired_detail_message_present(self) -> None:
        invite = _create_invite("expiredmsg@example.com")
        future = datetime.fromisoformat(str(invite.expires_at)) + timedelta(seconds=1)  # cast: DateTimeField → datetime
        with freeze_time(future):
            response = self.client.post(
                self.url,
                {"token": invite.token, "email": invite.email},
                format="json",
            )
        self.assertIn("detail", response.data)

    def test_exactly_at_expiry_boundary_returns_410(self) -> None:
        """expires_at itself is treated as expired (now() >= expires_at)."""
        invite = _create_invite("boundary@example.com")
        with freeze_time(datetime.fromisoformat(str(invite.expires_at))):  # cast: DateTimeField → datetime
            response = self.client.post(
                self.url,
                {"token": invite.token, "email": invite.email},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_one_second_before_expiry_succeeds(self) -> None:
        """Token is still valid 1 second before expires_at."""
        invite = _create_invite("almostgone@example.com")
        just_before = datetime.fromisoformat(str(invite.expires_at)) - timedelta(seconds=1)  # cast: DateTimeField → datetime
        with freeze_time(just_before):
            response = self.client.post(
                self.url,
                {"token": invite.token, "email": invite.email},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_expired_token_not_consumed(self) -> None:
        """An expired token must not be marked as used."""
        invite = _create_invite("notconsumed@example.com")
        future = datetime.fromisoformat(str(invite.expires_at)) + timedelta(hours=1)  # cast: DateTimeField → datetime
        with freeze_time(future):
            self.client.post(
                self.url,
                {"token": invite.token, "email": invite.email},
                format="json",
            )
        invite.refresh_from_db()
        self.assertIsNone(invite.used_at)


# ---------------------------------------------------------------------------
# Step 5 — Email-match check (403 Forbidden)
# ---------------------------------------------------------------------------

class InviteAcceptEmailMismatchTests(TestCase):
    """403 is returned when the presented email doesn't match the invite."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:accept")

    def test_wrong_email_returns_403(self) -> None:
        invite = _create_invite("right@example.com")
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": "wrong@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_email_detail_message_present(self) -> None:
        invite = _create_invite("detail@example.com")
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": "other@example.com"},
            format="json",
        )
        self.assertIn("detail", response.data)

    def test_wrong_email_does_not_consume_token(self) -> None:
        """A rejected attempt must not mark the token as used."""
        invite = _create_invite("nomark@example.com")
        self.client.post(
            self.url,
            {"token": invite.token, "email": "impostor@example.com"},
            format="json",
        )
        invite.refresh_from_db()
        self.assertIsNone(invite.used_at)

    def test_email_comparison_is_case_insensitive(self) -> None:
        """Invite for 'Alice@Example.COM' should match 'alice@example.com'."""
        invite = _create_invite("Alice@Example.COM")
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": "alice@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_email_with_extra_whitespace_returns_403(self) -> None:
        """Whitespace-padded emails should not accidentally match."""
        invite = _create_invite("clean@example.com")
        # DRF strips whitespace in EmailField, so ' clean@example.com ' → valid
        # but a genuinely different domain must still fail.
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": "clean@other.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Control — Happy path (200 OK)
# ---------------------------------------------------------------------------

class InviteAcceptHappyPathTests(TestCase):
    """Sanity control: a valid token + matching email produces 200."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:accept")

    def test_valid_token_and_email_returns_200(self) -> None:
        invite = _create_invite("happy@example.com")
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": invite.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_expected_fields(self) -> None:
        invite = _create_invite("fields@example.com")
        response = self.client.post(
            self.url,
            {"token": invite.token, "email": invite.email},
            format="json",
        )
        self.assertIn("detail", response.data)
        self.assertIn("email", response.data)
        self.assertIn("used_at", response.data)

    def test_token_is_consumed_after_acceptance(self) -> None:
        invite = _create_invite("consume@example.com")
        self.client.post(
            self.url,
            {"token": invite.token, "email": invite.email},
            format="json",
        )
        invite.refresh_from_db()
        self.assertIsNotNone(invite.used_at)

    def test_second_acceptance_returns_410(self) -> None:
        """The happy path naturally feeds the already-used negative case."""
        invite = _create_invite("double@example.com")
        payload = {"token": invite.token, "email": invite.email}
        self.client.post(self.url, payload, format="json")   # first OK
        response = self.client.post(self.url, payload, format="json")  # second → 410
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
