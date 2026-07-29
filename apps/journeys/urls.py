from django.urls import path

from apps.journeys import views

urlpatterns = [
    path("journey/advance/", views.journey_advance, name="journey_advance"),
    path("journey/regress/", views.journey_regress, name="journey_regress"),
    path("arrival/", views.arrival_guide, name="arrival_guide"),
]
