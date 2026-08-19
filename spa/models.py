"""Spa scheduling data models."""
import uuid
import string
import random

from django.db import models


def _generate_confirmation_code():
    """Generate a short, readable confirmation code like SPA-A3F9K."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=5))
    return f"SPA-{suffix}"


class ServiceCategory(models.TextChoices):
    MASSAGE = "MASSAGE", "Massage"
    FACIAL = "FACIAL", "Facial"
    BODY = "BODY", "Body Treatment"
    NAILS = "NAILS", "Nails"
    WELLNESS = "WELLNESS", "Wellness"


class AppointmentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"
    COMPLETED = "COMPLETED", "Completed"


class Service(models.Model):
    """A spa treatment or service offering."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(
        max_length=20,
        choices=ServiceCategory.choices,
        default=ServiceCategory.MASSAGE,
    )
    emoji = models.CharField(max_length=8, default="✨", help_text="Display emoji for the service card")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Therapist(models.Model):
    """A spa therapist who can perform services."""

    name = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    specialties = models.ManyToManyField(Service, blank=True, related_name="therapists")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Appointment(models.Model):
    """A booked spa appointment."""

    # Confirmation
    confirmation_code = models.CharField(
        max_length=12,
        unique=True,
        default=_generate_confirmation_code,
        editable=False,
    )

    # Customer
    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    # Booking details
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    therapist = models.ForeignKey(Therapist, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField()
    time_slot = models.TimeField()

    # Status
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-time_slot"]
        # Prevent double-booking the same therapist at the same time
        unique_together = [("therapist", "date", "time_slot")]

    def __str__(self):
        return f"{self.confirmation_code} — {self.customer_name} @ {self.date} {self.time_slot}"


class BlockedDate(models.Model):
    """A date when the spa is closed or blocked (e.g. holidays, special events)."""
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} - {self.reason or 'Blocked'}"


class Review(models.Model):
    """Customer ratings and feedback reviews."""
    customer_name = models.CharField(max_length=120)
    rating = models.PositiveIntegerField(default=5)  # 1 to 5 stars
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer_name} - {self.rating} Stars"


