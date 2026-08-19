"""Spa scheduling API views and frontend view."""
import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Appointment, AppointmentStatus, BlockedDate, Review, Service, Therapist
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

        try:
            therapist = Therapist.objects.get(pk=therapist_id)
        except Therapist.DoesNotExist:
            return Response(
                {"detail": "Therapist not found."},
                status=status.HTTP_404_NOT_FOUND,
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

        # Check therapist availability days (isoweekday: Mon=1, Sun=7)
        iso_wd = str(target_date.isoweekday())
        allowed_days = [d.strip() for d in therapist.working_days.split(",") if d.strip()]
        if iso_wd not in allowed_days:
            return Response({
                "date": date_str,
                "slots": [],
                "closed": True,
                "reason": f"{therapist.name} is off-duty on this day."
            })

        # Generate therapist's custom slots
        slot_minutes: int = getattr(settings, "SPA_SLOT_MINUTES", 60)
        all_slots = []
        current = therapist.working_hours_start
        close = therapist.working_hours_end
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
        user = request.user if request.user.is_authenticated else None
        appointment = serializer.save(user=user)
        read_serializer = AppointmentSerializer(appointment)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class AppointmentHistoryView(APIView):
    """
    GET /spa/api/appointments/?email=<email>
    Return all appointments for a given customer email.
    """

    def get(self, request: Request) -> Response:
        if request.user.is_authenticated:
            appointments = (
                Appointment.objects.filter(user=request.user)
                .select_related("service", "therapist")
                .order_by("-date", "-time_slot")
            )
        else:
            email = request.query_params.get("email", "").strip().lower()
            if not email:
                return Response(
                    {"detail": "'email' query param is required for guests."},
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

        old_status = appt.status
        new_status = serializer.validated_data["status"]
        appt.status = new_status
        appt.save(update_fields=["status", "updated_at"])

        # Send email when status changes to CONFIRMED
        if new_status == AppointmentStatus.CONFIRMED and old_status != AppointmentStatus.CONFIRMED:
            _send_confirmation_email(appt)

        return Response(AppointmentSerializer(appt).data)


# ────────────────────────────────────────────────────────────────────────────────
# Email notification helper
# ────────────────────────────────────────────────────────────────────────────────

def _send_confirmation_email(appt: Appointment) -> None:
    """Send booking confirmation email to the customer."""
    subject = f"MIKE J SPA — Appointment Confirmed 🌸 [{appt.confirmation_code}]"
    message = (
        f"Dear {appt.customer_name},\n\n"
        f"Your appointment at MIKE J SPA has been confirmed!\n\n"
        f"  Treatment : {appt.service.emoji} {appt.service.name}\n"
        f"  Therapist : {appt.therapist.name}\n"
        f"  Date      : {appt.date.strftime('%A, %d %B %Y')}\n"
        f"  Time      : {appt.time_slot.strftime('%I:%M %p')}\n\n"
        f"Confirmation Code: {appt.confirmation_code}\n"
        f"Please save this code — you can use it to look up your booking.\n\n"
        f"See you soon!\nMIKE J SPA Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@mikejspa.com"),
            recipient_list=[appt.customer_email],
            fail_silently=True,  # Don't break the status update if email fails
        )
    except Exception:
        pass  # Log silently — email failure must not break the API


# ────────────────────────────────────────────────────────────────────────────────
# Reviews API
# ────────────────────────────────────────────────────────────────────────────────

class ReviewListCreateView(APIView):
    """
    GET /spa/api/reviews/  — list recent reviews
    POST /spa/api/reviews/ — submit a new review
    """

    def get(self, request: Request) -> Response:
        reviews = Review.objects.all()[:50]
        data = [
            {
                "id": r.id,
                "customer_name": r.customer_name,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.strftime("%B %Y"),
            }
            for r in reviews
        ]
        return Response(data)

    def post(self, request: Request) -> Response:
        name = (request.data.get("customer_name") or "").strip()
        rating = request.data.get("rating", 5)
        comment = (request.data.get("comment") or "").strip()

        if not name or not comment:
            return Response(
                {"detail": "Name and comment are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rating = int(rating)
            if not 1 <= rating <= 5:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {"detail": "Rating must be between 1 and 5."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        review = Review.objects.create(
            customer_name=name,
            rating=rating,
            comment=comment,
        )
        return Response(
            {
                "id": review.id,
                "customer_name": review.customer_name,
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at.strftime("%B %Y"),
            },
            status=status.HTTP_201_CREATED,
        )


# ────────────────────────────────────────────────────────────────────────────────
# Separate Admin Dashboard & Blocked Dates views
# ─────────────────────────────────────────────────────────────────────────────

class SpaStaffPortalView(View):
    """Serve the therapist staff portal."""

    def get(self, request):
        return render(request, "spa/staff_portal.html")


class SpaAdminPortalView(View):
    """Serve the master administrator portal."""

    def get(self, request):
        return render(request, "spa/admin_portal.html")


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


# ─────────────────────────────────────────────────────────────────────────────
# Authentication APIs
# ─────────────────────────────────────────────────────────────────────────────

class CustomerRegisterView(APIView):
    """
    POST /spa/api/auth/register/
    Register a new customer account.
    """
    def post(self, request: Request) -> Response:
        name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not name or not email or not password:
            return Response({"detail": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=email).exists():
            return Response({"detail": "An account with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Create user
        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = name
        user.save()

        # Log user in
        login(request, user)

        return Response({
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip() or user.username,
            "email": user.email,
            "role": "customer"
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """
    POST /spa/api/auth/login/
    Log in customer, staff, or admin.
    """
    def post(self, request: Request) -> Response:
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not email or not password:
            return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=email, password=password)
        if user is None:
            # Fallback to local admin check if SPA_ADMIN_PASSWORD matches
            expected_admin_pw = getattr(settings, "SPA_ADMIN_PASSWORD", "77510438")
            if email == "admin@mikejspa.com" and password == expected_admin_pw:
                # Get or create superuser for convenience
                user, _ = User.objects.get_or_create(
                    username="admin@mikejspa.com",
                    defaults={"email": "admin@mikejspa.com", "is_superuser": True, "is_staff": True}
                )
                if not user.password:
                    user.set_password(expected_admin_pw)
                    user.save()
                user = authenticate(request, username="admin@mikejspa.com", password=expected_admin_pw)

        if user is not None:
            login(request, user)
            role = "customer"
            if user.is_superuser or user.is_staff:
                role = "admin"
            elif hasattr(user, "therapist_profile"):
                role = "staff"

            return Response({
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}".strip() or user.username,
                "email": user.email,
                "role": role
            })
        else:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    """
    POST /spa/api/auth/logout/
    Log out active session.
    """
    def post(self, request: Request) -> Response:
        logout(request)
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """
    GET /spa/api/auth/me/
    Get current logged in user details.
    """
    def get(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response({"authenticated": False}, status=status.HTTP_200_OK)

        user = request.user
        role = "customer"
        therapist_id = None
        
        if user.is_superuser or user.is_staff:
            role = "admin"
        elif hasattr(user, "therapist_profile"):
            role = "staff"
            therapist_id = user.therapist_profile.id

        return Response({
            "authenticated": True,
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip() or user.username,
            "email": user.email,
            "role": role,
            "therapist_id": therapist_id
        })


# ─────────────────────────────────────────────────────────────────────────────
# Appointment Rescheduling & Payment
# ─────────────────────────────────────────────────────────────────────────────

class AppointmentRescheduleView(APIView):
    """
    POST /spa/api/appointments/<str:code>/reschedule/
    Reschedule an existing appointment to a new date and time slot.
    """
    def post(self, request: Request, code: str) -> Response:
        try:
            appt = Appointment.objects.get(confirmation_code=code)
        except Appointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        new_date_str = request.data.get("date")
        new_time_str = request.data.get("time_slot")

        if not new_date_str or not new_time_str:
            return Response({"detail": "Both date and time_slot are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_date = datetime.date.fromisoformat(new_date_str)
            # Support time string as HH:MM or HH:MM:SS
            if len(new_time_str) == 5:
                new_time_str += ":00"
            new_time = datetime.time.fromisoformat(new_time_str)
        except ValueError:
            return Response({"detail": "Invalid date or time format."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce Sunday check
        if new_date.weekday() == 6:
            return Response({"detail": "We are closed on Sundays."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce BlockedDate/Holiday check
        if BlockedDate.objects.filter(date=new_date).exists():
            return Response({"detail": "The spa is closed on this date."}, status=status.HTTP_400_BAD_REQUEST)

        # Check therapist availability
        therapist = appt.therapist
        iso_wd = str(new_date.isoweekday())
        allowed_days = [d.strip() for d in therapist.working_days.split(",") if d.strip()]
        if iso_wd not in allowed_days:
            return Response({"detail": f"{therapist.name} is off-duty on this day."}, status=status.HTTP_400_BAD_REQUEST)

        if not (therapist.working_hours_start <= new_time < therapist.working_hours_end):
            return Response({"detail": "Requested time is outside therapist working hours."}, status=status.HTTP_400_BAD_REQUEST)

        # Check double-booking
        if Appointment.objects.filter(
            therapist=therapist,
            date=new_date,
            time_slot=new_time
        ).exclude(pk=appt.pk).exclude(status=AppointmentStatus.CANCELLED).exists():
            return Response({"detail": "This slot is already booked for this therapist."}, status=status.HTTP_400_BAD_REQUEST)

        # Apply reschedule
        appt.date = new_date
        appt.time_slot = new_time
        appt.status = AppointmentStatus.PENDING # Reset to pending for approval if rescheduled
        appt.save(update_fields=["date", "time_slot", "status", "updated_at"])

        return Response(AppointmentSerializer(appt).data)


class AppointmentPaymentView(APIView):
    """
    POST /spa/api/appointments/<str:code>/pay/
    Simulate processing credit card payment for a booking.
    """
    def post(self, request: Request, code: str) -> Response:
        try:
            appt = Appointment.objects.get(confirmation_code=code)
        except Appointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        method = request.data.get("method", "Card")
        # Simulate payment success
        appt.payment_status = "PAID"
        appt.payment_method = method
        appt.save(update_fields=["payment_status", "payment_method", "updated_at"])

        return Response({
            "detail": "Payment successful.",
            "payment_status": appt.payment_status,
            "payment_method": appt.payment_method
        })


# ─────────────────────────────────────────────────────────────────────────────
# Staff Capabilities
# ─────────────────────────────────────────────────────────────────────────────

class StaffAvailabilityUpdateView(APIView):
    """
    PATCH /spa/api/staff/availability/
    Logged-in staff updates their working hours and working days.
    """
    def patch(self, request: Request) -> Response:
        if not request.user.is_authenticated or not hasattr(request.user, "therapist_profile"):
            return Response({"detail": "Forbidden. Staff only."}, status=status.HTTP_403_FORBIDDEN)

        therapist = request.user.therapist_profile
        days = request.data.get("working_days")
        start_str = request.data.get("working_hours_start")
        end_str = request.data.get("working_hours_end")

        if days is not None:
            therapist.working_days = days
        if start_str is not None:
            try:
                therapist.working_hours_start = datetime.time.fromisoformat(start_str)
            except ValueError:
                return Response({"detail": "Invalid start time format."}, status=status.HTTP_400_BAD_REQUEST)
        if end_str is not None:
            try:
                therapist.working_hours_end = datetime.time.fromisoformat(end_str)
            except ValueError:
                return Response({"detail": "Invalid end time format."}, status=status.HTTP_400_BAD_REQUEST)

        therapist.save()
        return Response({
            "working_days": therapist.working_days,
            "working_hours_start": therapist.working_hours_start.strftime("%H:%M"),
            "working_hours_end": therapist.working_hours_end.strftime("%H:%M")
        })


# ─────────────────────────────────────────────────────────────────────────────
# Admin Services & Users Management & Reports
# ─────────────────────────────────────────────────────────────────────────────

class AdminServiceDetailView(APIView):
    """
    PUT /spa/api/admin/services/<id>/
    Edit service price/duration/description.

    DELETE /spa/api/admin/services/<id>/
    Deactivate a service.
    """
    def put(self, request: Request, pk: int) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        try:
            service = Service.objects.get(pk=pk)
        except Service.DoesNotExist:
            return Response({"detail": "Service not found."}, status=status.HTTP_404_NOT_FOUND)

        service.name = request.data.get("name", service.name)
        service.description = request.data.get("description", service.description)
        service.price = request.data.get("price", service.price)
        service.duration_minutes = request.data.get("duration_minutes", service.duration_minutes)
        service.category = request.data.get("category", service.category)
        service.emoji = request.data.get("emoji", service.emoji)
        service.is_active = request.data.get("is_active", service.is_active)
        service.save()

        return Response(ServiceSerializer(service).data)

    def delete(self, request: Request, pk: int) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        try:
            service = Service.objects.get(pk=pk)
            # Soft delete/deactivate to avoid breaking existing appointment links
            service.is_active = False
            service.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Service.DoesNotExist:
            return Response({"detail": "Service not found."}, status=status.HTTP_404_NOT_FOUND)


# Allow adding new services for admins
class ServiceListView(APIView):
    """
    GET /spa/api/services/
    POST /spa/api/services/ (Admin Only) - create a new service.
    """
    def get(self, request: Request) -> Response:
        services = Service.objects.filter(is_active=True)
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get("name")
        price = request.data.get("price")
        duration = request.data.get("duration_minutes", 60)
        category = request.data.get("category", "MASSAGE")
        emoji = request.data.get("emoji", "✨")
        desc = request.data.get("description", "")

        if not name or not price:
            return Response({"detail": "Name and price are required."}, status=status.HTTP_400_BAD_REQUEST)

        service = Service.objects.create(
            name=name, price=price, duration_minutes=duration,
            category=category, emoji=emoji, description=desc
        )
        return Response(ServiceSerializer(service).data, status=status.HTTP_201_CREATED)


class AdminUserListView(APIView):
    """
    GET /spa/api/admin/users/
    List all customer and therapist user accounts.

    POST /spa/api/admin/users/
    Create a new user account.
    """
    def get(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.all().order_by("username")
        data = []
        for u in users:
            role = "customer"
            therapist_id = None
            if u.is_superuser or u.is_staff:
                role = "admin"
            elif hasattr(u, "therapist_profile"):
                role = "staff"
                therapist_id = u.therapist_profile.id

            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "name": f"{u.first_name} {u.last_name}".strip() or u.username,
                "role": role,
                "therapist_id": therapist_id
            })
        return Response(data)

    def post(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        role = request.data.get("role", "customer")  # customer or staff

        if not email or not password:
            return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=email).exists():
            return Response({"detail": "User already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = name
        
        if role == "admin":
            user.is_staff = True
            user.is_superuser = True
        user.save()

        if role == "staff":
            # Check if therapist profile exists or create it
            therapist, _ = Therapist.objects.get_or_create(
                name=name or email,
                defaults={"user": user, "bio": "Therapist bio details…"}
            )
            if not therapist.user:
                therapist.user = user
                therapist.save()

        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": name,
            "role": role
        }, status=status.HTTP_201_CREATED)


class AdminReportsView(APIView):
    """
    GET /spa/api/admin/reports/
    Generate analytical reports on revenue and booking metrics.
    """
    def get(self, request: Request) -> Response:
        if not _check_admin_password(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        active_appts = Appointment.objects.exclude(status="CANCELLED")
        
        # 1. Booking Metrics
        total_bookings = active_appts.count()
        pending_bookings = active_appts.filter(status="PENDING").count()
        confirmed_bookings = active_appts.filter(status="CONFIRMED").count()
        completed_bookings = active_appts.filter(status="COMPLETED").count()

        # 2. Revenue (Sum of prices of active bookings)
        total_revenue = sum(a.service.price for a in active_appts if a.status in ["CONFIRMED", "COMPLETED"])

        # 3. Popular Services
        service_counts = {}
        for a in active_appts:
            name = a.service.name
            service_counts[name] = service_counts.get(name, 0) + 1
        
        popular_services = [{"name": k, "count": v} for k, v in sorted(service_counts.items(), key=lambda item: item[1], reverse=True)[:5]]

        # 4. Monthly Bookings volume mapping
        monthly_bookings = {}
        for a in active_appts:
            # e.g., "August 2026"
            month_key = a.date.strftime("%B %Y")
            monthly_bookings[month_key] = monthly_bookings.get(month_key, 0) + 1
        
        monthly_stats = [{"month": k, "count": v} for k, v in monthly_bookings.items()]

        return Response({
            "metrics": {
                "total_bookings": total_bookings,
                "pending": pending_bookings,
                "confirmed": confirmed_bookings,
                "completed": completed_bookings,
                "total_revenue": float(total_revenue),
                "total_users": User.objects.count(),
                "total_services": Service.objects.filter(is_active=True).count()
            },
            "popular_services": popular_services,
            "monthly_stats": monthly_stats
        })

