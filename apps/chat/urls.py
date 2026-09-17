from django.urls import path

from apps.chat import views

urlpatterns = [
    path("chat/send/", views.chat_send, name="chat_send"),
    path("chat/live-log/", views.live_log, name="chat_live_log"),
]
