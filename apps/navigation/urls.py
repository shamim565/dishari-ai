from django.urls import path

from apps.navigation import views

urlpatterns = [
    path("map/", views.airport_map, name="airport_map"),
    path("navigate/", views.navigate, name="navigate"),
    path("scan/<str:code>/", views.scan_marker, name="scan_marker"),
    path("lost/", views.lost, name="lost"),
]
