from django.urls import path

from apps.voice import views

urlpatterns = [
    path("api/voice/tts/", views.tts, name="voice_tts"),
    path("api/voice/stt/", views.stt, name="voice_stt"),
    path("api/voice/status/", views.tts_status, name="voice_status"),
    path("api/voice/live-token/", views.live_token, name="voice_live_token"),
    path("api/voice/live-context/", views.live_context, name="voice_live_context"),
]
