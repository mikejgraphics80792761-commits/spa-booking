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
    SpaStaffPortalView,
    SpaAdminPortalView,
    AdminBlockedDateListView,
    AdminBlockedDateDeleteView,
    ReviewListCreateView,
    CustomerRegisterView,
    UserLoginView,
    UserLogoutView,
    CurrentUserView,
    AppointmentRescheduleView,
    AppointmentPaymentView,
    StaffAvailabilityUpdateView,
    AdminServiceDetailView,
    AdminUserListView,
    AdminReportsView,
)

app_name = "spa"

urlpatterns = [
    # Frontend
    path("", SpaIndexView.as_view(), name="index"),
    path("staff-portal/", SpaStaffPortalView.as_view(), name="staff-portal"),
    path("admin-portal/", SpaAdminPortalView.as_view(), name="admin-portal"),

    # Auth
    path("api/auth/register/", CustomerRegisterView.as_view(), name="auth-register"),
    path("api/auth/login/", UserLoginView.as_view(), name="auth-login"),
    path("api/auth/logout/", UserLogoutView.as_view(), name="auth-logout"),
    path("api/auth/me/", CurrentUserView.as_view(), name="auth-me"),

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
    path("api/appointments/<str:code>/reschedule/", AppointmentRescheduleView.as_view(), name="appointment-reschedule"),
    path("api/appointments/<str:code>/pay/", AppointmentPaymentView.as_view(), name="appointment-pay"),

    # Staff
    path("api/staff/availability/", StaffAvailabilityUpdateView.as_view(), name="staff-availability"),

    # Admin
    path("api/admin/appointments/", AdminAppointmentListView.as_view(), name="admin-appointments"),
    path("api/admin/appointments/<int:pk>/status/", AdminAppointmentStatusView.as_view(), name="admin-appointment-status"),
    path("api/admin/blocked-dates/", AdminBlockedDateListView.as_view(), name="admin-blocked-dates"),
    path("api/admin/blocked-dates/<int:pk>/", AdminBlockedDateDeleteView.as_view(), name="admin-blocked-date-delete"),
    path("api/admin/services/<int:pk>/", AdminServiceDetailView.as_view(), name="admin-service-detail"),
    path("api/admin/users/", AdminUserListView.as_view(), name="admin-users"),
    path("api/admin/reports/", AdminReportsView.as_view(), name="admin-reports"),

    # Reviews
    path("api/reviews/", ReviewListCreateView.as_view(), name="reviews"),
]
