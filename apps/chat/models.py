from django.db import models

from apps.journeys.models import JourneySession


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [(ROLE_USER, "User"), (ROLE_ASSISTANT, "Assistant")]

    SOURCE_LLM = "llm"
    SOURCE_DEMO = "demo"
    SOURCE_CHOICES = [(SOURCE_LLM, "LLM"), (SOURCE_DEMO, "Demo responder")]

    journey = models.ForeignKey(
        JourneySession, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages"
    )
    session_key = models.CharField(max_length=40, blank=True, default="", db_index=True)
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    lang = models.CharField(max_length=2, default="en")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_LLM)
    created_at = models.DateTimeField(auto_now_add=True)
