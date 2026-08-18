"""Invite token utility functions."""
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone


def generate_token() -> str:
    """Return a cryptographically-secure URL-safe token (43 chars)."""
    return secrets.token_urlsafe(32)


def get_expiry() -> datetime:
    """Return a timezone-aware expiry datetime from now."""
    hours = getattr(settings, "INVITE_EXPIRY_HOURS", 72)
    return timezone.now() + timedelta(hours=hours)
