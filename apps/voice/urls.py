from django.urls import path

from apps.voice import views

urlpatterns = [
    path("api/voice/tts/", views.tts, name="voice_tts"),
