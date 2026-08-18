"""Spa app configuration."""
from django.apps import AppConfig


class SpaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "spa"
    verbose_name = "Spa Scheduling"
