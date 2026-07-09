from django.urls import path

from apps.core import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("lang/<str:code>/", views.set_lang, name="set_lang"),
