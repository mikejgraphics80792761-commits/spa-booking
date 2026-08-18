"""Django app config for invites."""
from __future__ import annotations

from typing import ClassVar

from django.apps import AppConfig


class InvitesConfig(AppConfig):
    default_auto_field: ClassVar[str] = "django.db.models.BigAutoField"
    name = "invites"
