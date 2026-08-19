"""Spa scheduling API views and frontend view."""
import datetime

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Appointment, AppointmentStatus, Service, Therapist, BlockedDate
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AppointmentStatusUpdateSerializer,
    ServiceSerializer,
    TherapistSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Frontend
# ─────────────────────────────────────────────────────────────────────────────

class SpaIndexView(View):
    """Serve the single-page spa frontend."""

    def get(self, request):
        return render(request, "spa/index.html")


# ─────────────────────────────────────────────────────────────────────────────
# Services API
# ─────────────────────────────────────────────────────────────────────────────

class ServiceListView(APIView):
    """
    GET /spa/api/services/
    Returns all active services.
    """

    def get(self, request: Request) -> Response:
        services = Service.objects.filter(is_active=True)
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Therapists API
# ─────────────────────────────────────────────────────────────────────────────

class TherapistListView(APIView):
    """
    GET /spa/api/therapists/?service=<id>
    Returns therapists; filters by service if `service` query param given.
    """

    def get(self, request: Request) -> Response:
        qs = Therapist.objects.filter(is_active=True).prefetch_related("specialties")
        service_id = request.query_params.get("service")
        if service_id:
            qs = qs.filter(specialties__id=service_id)
        serializer = TherapistSerializer(qs, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Availability API
# ─────────────────────────────────────────────────────────────────────────────

class AvailabilityView(APIView):
    """
    GET /spa/api/availability/?therapist=<id>&date=YYYY-MM-DD
    Returns list of available time slots (HH:MM) for a therapist on a date.
    """

    def get(self, request: Request) -> Response:
        therapist_id = request.query_params.get("therapist")
        date_str = request.query_params.get("date")

        if not therapist_id or not date_str:
            return Response(
                {"detail": "Both 'therapist' and 'date' query params are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reject dates in the past
        if target_date < timezone.now().date():
            return Response({"slots": []})

        # Reject Sundays
        if target_date.weekday() == 6:
            return Response({
                "date": date_str,
                "slots": [],
                "closed": True,
                "reason": "Closed on Sundays"
            })

        # Reject Blocked/Holiday dates
        blocked = BlockedDate.objects.filter(date=target_date).first()
        if blocked:
            return Response({
                "date": date_str,
                "slots": [],
                "closed": True,
                "reason": blocked.reason or "Closed (Holiday/Special Event)"
            })

        # Generate all possible slots for the day
        open_hour: int = getattr(settings, "SPA_OPEN_HOUR", 9)
        close_hour: int = getattr(settings, "SPA_CLOSE_HOUR", 18)
        slot_minutes: int = getattr(settings, "SPA_SLOT_MINUTES", 60)

        all_slots = []
        current = datetime.time(open_hour, 0)
        close = datetime.time(close_hour, 0)
        while current < close:
            all_slots.append(current)
            dt = datetime.datetime.combine(datetime.date.today(), current)
            dt += datetime.timedelta(minutes=slot_minutes)
            current = dt.time()

        # Fetch already-booked (non-cancelled) slots for this therapist/date
        booked = set(
            Appointment.objects.filter(
                therapist_id=therapist_id,
                date=target_date,
            )
            .exclude(status=AppointmentStatus.CANCELLED)
            .values_list("time_slot", flat=True)
        )

        available = [s.strftime("%H:%M") for s in all_slots if s not in booked]
        return Response({"date": date_str, "slots": available})


# ─────────────────────────────────────────────────────────────────────────────
# Appointments API
# ─────────────────────────────────────────────────────────────────────────────

class AppointmentCreateView(APIView):
    """
    POST /spa/api/appointments/
    Create a new booking.
    """

    def post(self, request: Request) -> Response:
        serializer = AppointmentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment = serializer.save()
        read_serializer = AppointmentSerializer(appointment)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class AppointmentHistoryView(APIView):
    """
    GET /spa/api/appointments/?email=<email>
    Return all appointments for a given customer email.
    """

    def get(self, request: Request) -> Response:
        email = request.query_params.get("email", "").strip().lower()
        if not email:
            return Response(
                {"detail": "'email' query param is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointments = (
            Appointment.objects.filter(customer_email__iexact=email)
            .select_related("service", "therapist")
            .order_by("-date", "-time_slot")
        )
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)


class AppointmentDetailView(APIView):
    """
    GET  /spa/api/appointments/<code>/
    Return a single appointment by confirmation code.
    """

    def _get_appointment(self, code: str):
        try:
            return Appointment.objects.select_related("service", "therapist").get(
                confirmation_code=code
            )
        except Appointment.DoesNotExist:
            return None

    def get(self, request: Request, code: str) -> Response:
        appt = self._get_appointment(code)
        if not appt:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentSerializer(appt).data)


class AppointmentCancelView(APIView):
    """
    PATCH /spa/api/appointments/<code>/cancel/
    Cancel a booking by confirmation code.
    """

    def patch(self, request: Request, code: str) -> Response:
        try:
            appt = Appointment.objects.get(confirmation_code=code)
        except Appointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        if appt.status == AppointmentStatus.CANCELLED:
            return Response({"detail": "Appointment is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        if appt.status == AppointmentStatus.COMPLETED:
            return Response({"detail": "Cannot cancel a completed appointment."}, status=status.HTTP_400_BAD_REQUEST)

        appt.status = AppointmentStatus.CANCELLED
        appt.save(update_fields=["status", "updated_at"])
        return Response(AppointmentSerializer(appt).data)


# ─────────────────────────────────────────────────────────────────────────────
# Admin API  (demo-password protected)
# ─────────────────────────────────────────────────────────────────────────────

def _check_admin_password(request: Request) -> bool:
    """Simple demo password check via Authorization header or query param."""
    expected = getattr(settings, "SPA_ADMIN_PASSWORD", "spa-admin-2026")
    auth_header = request.headers.get("X-Admin-Password", "")
    query_param = request.query_params.get("admin_password", "")
    return auth_header == expected or query_param == expected


class AdminAppointmentListView(APIView):
    """
    GET /spa/api/admin/appointments/?admin_password=...
    List all appointments with optional status filter.
    """

    def get(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        qs = Appointment.objects.select_related("service", "therapist").order_by("-date", "-time_slot")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        serializer = AppointmentSerializer(qs, many=True)
        return Response(serializer.data)


class AdminAppointmentStatusView(APIView):
    """
    PATCH /spa/api/admin/appointments/<id>/status/?admin_password=...
    Update appointment status.
    """

    def patch(self, request: Request, pk: int) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        try:
            appt = Appointment.objects.select_related("service", "therapist").get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AppointmentStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appt.status = serializer.validated_data["status"]
        appt.save(update_fields=["status", "updated_at"])
        return Response(AppointmentSerializer(appt).data)


# ─────────────────────────────────────────────────────────────────────────────
# Separate Admin Dashboard & Blocked Dates views
# ─────────────────────────────────────────────────────────────────────────────

class SpaAdminDashboardView(View):
    """Serve the single-page admin dashboard."""

    def get(self, request):
        return render(request, "spa/admin_dashboard.html")


class AdminBlockedDateListView(APIView):
    """
    GET /spa/api/admin/blocked-dates/?admin_password=...
    List all blocked dates.

    POST /spa/api/admin/blocked-dates/?admin_password=...
    Create a new blocked date/holiday.
    """

    def get(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
        blocked_dates = BlockedDate.objects.all().order_by("date")
        data = [{"id": b.id, "date": b.date.isoformat(), "reason": b.reason} for b in blocked_dates]
        return Response(data)

    def post(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
        
        date_str = request.data.get("date")
        reason = request.data.get("reason", "")
        
        if not date_str:
            return Response({"detail": "Date is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return Response({"detail": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)
            
        blocked_date, created = BlockedDate.objects.get_or_create(
            date=target_date,
            defaults={"reason": reason}
        )
        if not created:
            blocked_date.reason = reason
            blocked_date.save()
            
        return Response({
            "id": blocked_date.id,
            "date": blocked_date.date.isoformat(),
            "reason": blocked_date.reason
        }, status=status.HTTP_201_CREATED)


class AdminBlockedDateDeleteView(APIView):
    """
    DELETE /spa/api/admin/blocked-dates/<int:pk>/?admin_password=...
    Delete a blocked date (unblock).
    """

    def delete(self, request: Request, pk: int) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            blocked_date = BlockedDate.objects.get(pk=pk)
            blocked_date.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BlockedDate.DoesNotExist:
            return Response({"detail": "Blocked date not found."}, status=status.HTTP_404_NOT_FOUND)
