from django.urls import path

from apps.notifications import views

urlpatterns = [
    path("notifications/", views.notifications_page, name="notifications"),
    path("api/notifications/", views.api_events, name="api_notifications"),
    path("ops/", views.ops_panel, name="ops_panel"),
    path("ops/login/", views.ops_login, name="ops_login"),
    path("ops/logout/", views.ops_logout, name="ops_logout"),
    path("ops/flight/<int:pk>/<slug:action>/", views.ops_action, name="ops_action"),
    path("ops/reset/", views.ops_reset, name="ops_reset"),
    path("ops/clear-events/", views.ops_clear_events, name="ops_clear_events"),
]
