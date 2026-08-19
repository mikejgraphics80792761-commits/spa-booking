"""Spa admin configuration."""
from django.contrib import admin

from .models import Appointment, BlockedDate, Review, Service, Therapist


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "duration_minutes", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name"]


@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    filter_horizontal = ["specialties"]
    search_fields = ["name"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        "confirmation_code",
        "customer_name",
        "customer_email",
        "service",
        "therapist",
        "date",
        "time_slot",
        "status",
        "created_at",
    ]
    list_filter = ["status", "date", "service", "therapist"]
    search_fields = ["confirmation_code", "customer_name", "customer_email"]
    readonly_fields = ["confirmation_code", "created_at", "updated_at"]
    ordering = ["-date", "-time_slot"]


@admin.register(BlockedDate)
class BlockedDateAdmin(admin.ModelAdmin):
    list_display = ["date", "reason", "created_at"]
    ordering = ["date"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["customer_name", "rating", "comment", "created_at"]
    list_filter = ["rating"]
    search_fields = ["customer_name", "comment"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
