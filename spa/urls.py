"""Spa app URL routing."""
from django.urls import path

from .views import (
    AdminAppointmentListView,
    AdminAppointmentStatusView,
    AppointmentCancelView,
    AppointmentCreateView,
    AppointmentDetailView,
    AppointmentHistoryView,
    AvailabilityView,
    ServiceListView,
    SpaIndexView,
    TherapistListView,
    SpaAdminDashboardView,
    AdminBlockedDateListView,
    AdminBlockedDateDeleteView,
)

app_name = "spa"

urlpatterns = [
    # Frontend
    path("", SpaIndexView.as_view(), name="index"),
    path("admin-dashboard/", SpaAdminDashboardView.as_view(), name="admin-dashboard"),

    # Services
    path("api/services/", ServiceListView.as_view(), name="services"),

    # Therapists
    path("api/therapists/", TherapistListView.as_view(), name="therapists"),

    # Availability
    path("api/availability/", AvailabilityView.as_view(), name="availability"),

    # Appointments
    path("api/appointments/", AppointmentCreateView.as_view(), name="appointment-create"),
    path("api/appointments/history/", AppointmentHistoryView.as_view(), name="appointment-history"),
    path("api/appointments/<str:code>/", AppointmentDetailView.as_view(), name="appointment-detail"),
    path("api/appointments/<str:code>/cancel/", AppointmentCancelView.as_view(), name="appointment-cancel"),

    # Admin
    path("api/admin/appointments/", AdminAppointmentListView.as_view(), name="admin-appointments"),
    path("api/admin/appointments/<int:pk>/status/", AdminAppointmentStatusView.as_view(), name="admin-appointment-status"),
    path("api/admin/blocked-dates/", AdminBlockedDateListView.as_view(), name="admin-blocked-dates"),
    path("api/admin/blocked-dates/<int:pk>/", AdminBlockedDateDeleteView.as_view(), name="admin-blocked-date-delete"),
]
