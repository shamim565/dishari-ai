from django.urls import path

from apps.chat import views

urlpatterns = [
    path("chat/send/", views.chat_send, name="chat_send"),
