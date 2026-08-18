"""
Tests for POST /invites/create
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from invites.models import Invite


class InviteCreateHappyPathTests(TestCase):
    """Positive path: valid requests produce a token."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:create")

    def test_valid_email_returns_201(self) -> None:
        response = self.client.post(self.url, {"email": "alice@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_response_contains_token(self) -> None:
        response = self.client.post(self.url, {"email": "alice@example.com"}, format="json")
        self.assertIn("token", response.data)
        self.assertTrue(len(response.data["token"]) > 10)

    def test_response_contains_email_and_expires_at(self) -> None:
        response = self.client.post(self.url, {"email": "alice@example.com"}, format="json")
        self.assertIn("email", response.data)
        self.assertIn("expires_at", response.data)
        self.assertEqual(response.data["email"], "alice@example.com")

    def test_invite_persisted_in_database(self) -> None:
        self.client.post(self.url, {"email": "bob@example.com"}, format="json")
        self.assertEqual(Invite.objects.filter(email="bob@example.com").count(), 1)

    def test_each_invite_gets_unique_token(self) -> None:
        r1 = self.client.post(self.url, {"email": "a@example.com"}, format="json")
        r2 = self.client.post(self.url, {"email": "b@example.com"}, format="json")
        self.assertNotEqual(r1.data["token"], r2.data["token"])

    def test_invite_created_with_used_at_none(self) -> None:
        response = self.client.post(self.url, {"email": "carol@example.com"}, format="json")
        token = response.data["token"]
        invite = Invite.objects.get(token=token)
        self.assertIsNone(invite.used_at)


class InviteCreateValidationTests(TestCase):
    """Negative path: bad requests are rejected with 400."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("invites:create")

    def test_missing_email_returns_400(self) -> None:
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_invalid_email_format_returns_400(self) -> None:
        response = self.client.post(self.url, {"email": "not-an-email"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_email_string_returns_400(self) -> None:
        response = self.client.post(self.url, {"email": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_numeric_email_returns_400(self) -> None:
        response = self.client.post(self.url, {"email": 12345}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_body_returns_400(self) -> None:
        response = self.client.post(self.url, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
