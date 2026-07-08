from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.portal.urls")),
    path("", include("apps.tickets.urls")),
    path("", include("apps.journeys.urls")),
    path("", include("apps.navigation.urls")),
    path("", include("apps.chat.urls")),
    path("", include("apps.voice.urls")),
    path("", include("apps.notifications.urls")),
]
