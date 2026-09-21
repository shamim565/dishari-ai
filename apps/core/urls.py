from django.urls import path

from apps.core import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("lang/<str:code>/", views.set_lang, name="set_lang"),
    path("api/i18n/", views.i18n_json, name="i18n_json"),
    path("sw.js", views.service_worker, name="service_worker"),
]
