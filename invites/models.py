"""Invite model."""
from django.db import models
from django.utils import timezone

from .utils import generate_token, get_expiry


class Invite(models.Model):
    """
    Represents a single-use, expiring invite token tied to an email address.

    Lifecycle
    ---------
    - Created by a staff/admin user via POST /invites/create.
    - Consumed (used_at set) by a recipient via POST /invites/accept.
    - A token is considered *valid* when:
        1. used_at is None   (not yet consumed — single-use enforcement)
        2. now() < expires_at (not past the expiry window)
        3. The accepting email matches the invite email (email-match check)
    """

    email = models.EmailField(
        help_text="The email address this invite is intended for."
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generate_token,
        help_text="Cryptographically-secure URL-safe token.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        default=get_expiry,
        help_text="After this timestamp the token is no longer valid.",
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Set when the token is successfully accepted. None = unused.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "used" if self.used_at else ("expired" if self.is_expired else "valid")
        return f"Invite({self.email}, {status})"

    # ------------------------------------------------------------------
    # Computed properties (convenience; not used by views — they check
    # raw field values for clarity).
    # ------------------------------------------------------------------

    @property
    def is_used(self) -> bool:
        """True if this token has already been consumed."""
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        """True if the expiry window has passed."""
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        """True when the token can still be accepted."""
        return not self.is_used and not self.is_expired

    def consume(self) -> None:
        """Mark the token as used. Caller must call save()."""
        self.used_at = timezone.now()
