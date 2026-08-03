from django.urls import path

from apps.portal import views

urlpatterns = [
    path("", views.home, name="home"),
    path("assistant/", views.assistant, name="assistant"),
    path("session/end/", views.session_end, name="session_end"),
]
