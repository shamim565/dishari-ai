from django.urls import path

from apps.tickets import views

urlpatterns = [
    path("ticket/", views.ticket_upload, name="ticket_upload"),
    path("ticket/scan/", views.ticket_scan, name="ticket_scan"),
    path("ticket/demo/", views.ticket_demo, name="ticket_demo"),
    path("ticket/demo/<int:pk>/", views.ticket_demo_pick, name="ticket_demo_pick"),
    path("ticket/verified/", views.ticket_verified, name="ticket_verified"),
    path("ticket/handoff/<str:token>/status/", views.ticket_handoff_status, name="ticket_handoff_status"),
    path("ticket/handoff/<str:token>/hold/", views.ticket_handoff_hold, name="ticket_handoff_hold"),
    path("t/<str:token>/", views.ticket_phone, name="ticket_phone"),
    path("t/<str:token>/scan/", views.ticket_phone_scan, name="ticket_phone_scan"),
    path("t/<str:token>/ping/", views.ticket_phone_ping, name="ticket_phone_ping"),
]
