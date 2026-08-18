"""Root URL configuration."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("invites/", include("invites.urls")),
    path("spa/", include("spa.urls")),
]
