"""Invite API views."""
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Invite
from .serializers import InviteAcceptSerializer, InviteCreateSerializer


class InviteCreateView(APIView):
    """
    POST /invites/create

    Creates a single-use, expiring invite token for a given email address.

    Request body
    ------------
    {
        "email": "recipient@example.com"
    }

    Responses
    ---------
    201 Created     → token issued successfully
    400 Bad Request → invalid / missing email
    """

    def post(self, request: Request) -> Response:
        serializer = InviteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        invite = serializer.save()

        return Response(
            {
                "token": invite.token,
                "email": invite.email,
                "expires_at": invite.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class InviteAcceptView(APIView):
    """
    POST /invites/accept

    Validates and consumes an invite token.

    Validation chain (in order)
    ---------------------------
    1. Field-level validation (token + email present, well-formed) → 400
    2. Token lookup                                                → 404 if not found
    3. Single-use check  (used_at is None)                        → 410 if already used
    4. Expiry check      (now < expires_at)                       → 410 if expired
    5. Email-match check (email == invite.email)                  → 403 if mismatch

    On success the token is consumed (used_at set) and 200 is returned.

    Request body
    ------------
    {
        "token": "<invite token>",
        "email": "recipient@example.com"
    }

    Responses
    ---------
    200 OK            → invite accepted, token consumed
    400 Bad Request   → missing / malformed fields
    403 Forbidden     → email does not match the invite
    404 Not Found     → token does not exist
    410 Gone          → token already used OR expired
    """

    def post(self, request: Request) -> Response:
        # ── Step 1: field validation ────────────────────────────────────────
        serializer = InviteAcceptSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_value: str = serializer.validated_data["token"]
        email_value: str = serializer.validated_data["email"]

        # ── Step 2: token lookup ────────────────────────────────────────────
        try:
            invite = Invite.objects.get(token=token_value)
        except Invite.DoesNotExist:
            return Response(
                {"detail": "Invite token not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Step 3: single-use check ────────────────────────────────────────
        if invite.used_at is not None:
            return Response(
                {"detail": "This invite token has already been used."},
                status=status.HTTP_410_GONE,
            )

        # ── Step 4: expiry check ────────────────────────────────────────────
        if timezone.now() >= invite.expires_at:
            return Response(
                {"detail": "This invite token has expired."},
                status=status.HTTP_410_GONE,
            )

        # ── Step 5: email-match check ───────────────────────────────────────
        if email_value.lower() != invite.email.lower():
            return Response(
                {"detail": "Email address does not match the invite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Success: consume the token ──────────────────────────────────────
        invite.consume()
        invite.save(update_fields=["used_at"])

        return Response(
            {
                "detail": "Invite accepted.",
                "email": invite.email,
                "used_at": invite.used_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
