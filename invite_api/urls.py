"""Root URL configuration."""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/spa/", permanent=False)),
    path("admin/", admin.site.urls),
    path("invites/", include("invites.urls")),
    path("spa/", include("spa.urls")),
]
