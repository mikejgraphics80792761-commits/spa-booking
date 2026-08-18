"""Invites app URL configuration."""
from django.urls import path

from .views import InviteAcceptView, InviteCreateView

app_name = "invites"

urlpatterns = [
    path("create", InviteCreateView.as_view(), name="create"),
    path("accept", InviteAcceptView.as_view(), name="accept"),
]
