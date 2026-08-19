"""DRF serializers for the spa scheduling app."""
from rest_framework import serializers

from .models import Appointment, AppointmentStatus, Service, Therapist


class ServiceSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "duration_minutes",
            "price",
            "category",
            "category_display",
            "emoji",
            "is_active",
        ]


class TherapistSerializer(serializers.ModelSerializer):
    specialties = ServiceSerializer(many=True, read_only=True)
    specialty_ids = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        many=True,
        write_only=True,
        source="specialties",
        required=False,
    )

    class Meta:
        model = Therapist
        fields = ["id", "name", "bio", "specialties", "specialty_ids", "is_active"]


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Used when a customer creates a new booking."""

    class Meta:
        model = Appointment
        fields = [
            "customer_name",
            "customer_email",
            "customer_phone",
            "service",
            "therapist",
            "date",
            "time_slot",
            "notes",
        ]

    def validate(self, data):
        # Reject Sundays
        if data["date"].weekday() == 6:
            raise serializers.ValidationError(
                {"date": "We are closed on Sundays."}
            )

        # Reject Blocked/Holiday dates
        from .models import BlockedDate
        blocked = BlockedDate.objects.filter(date=data["date"]).first()
        if blocked:
            raise serializers.ValidationError(
                {"date": f"The spa is closed on this date: {blocked.reason or 'Holiday/Special Event'}."}
            )

        # Ensure the therapist offers the requested service
        therapist: Therapist = data["therapist"]
        service: Service = data["service"]
        if not therapist.specialties.filter(pk=service.pk).exists():
            raise serializers.ValidationError(
                {"therapist": f"{therapist.name} does not offer {service.name}."}
            )

        # Prevent double-booking
        if Appointment.objects.filter(
            therapist=therapist,
            date=data["date"],
            time_slot=data["time_slot"],
        ).exclude(status=AppointmentStatus.CANCELLED).exists():
            raise serializers.ValidationError(
                {"time_slot": "This time slot is already booked for that therapist."}
            )

        return data


class AppointmentSerializer(serializers.ModelSerializer):
    """Full read serializer — used for admin & customer history."""

    service = ServiceSerializer(read_only=True)
    therapist = TherapistSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "confirmation_code",
            "customer_name",
            "customer_email",
            "customer_phone",
            "service",
            "therapist",
            "date",
            "time_slot",
            "status",
            "status_display",
            "notes",
            "payment_status",
            "payment_method",
            "created_at",
            "updated_at",
        ]


class AppointmentStatusUpdateSerializer(serializers.Serializer):
    """Used by admin to update appointment status."""

    status = serializers.ChoiceField(choices=AppointmentStatus.choices)
