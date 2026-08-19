import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.chat.models import ChatMessage
from apps.flights.models import Flight


def parse_sse(content):
    events = []
    for line in content.decode("utf-8").split("\n\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


class ChatBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        call_command("seed_nav")

    def setUp(self):
        self.enterContext(patch("apps.chat.views.registry.chat_setup", return_value=None))

    def app_client(self, lang="en"):
        client = Client()
        session = client.session
        session["lang"] = lang
        session.save()
        return client


class DashboardVoicePanelTests(ChatBaseTests):
    def test_dashboard_hosts_assistant_frame(self):
        client = self.app_client()
        response = client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "assistant-frame")
        self.assertContains(response, "/assistant/")

    def test_assistant_page_serves_voice_panel(self):
        client = self.app_client()
        response = client.get(reverse("assistant"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "voice-mic")
        self.assertContains(response, "chat-config")


class AnonymousChatIsolationTests(ChatBaseTests):
    def start_journey(self, client, number="BG147"):
        flight = Flight.objects.get(number=number)
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))

    def test_anonymous_history_not_shared_between_sessions(self):
        a = self.app_client()
        b = self.app_client()
        response = a.post(reverse("chat_send"), {"message": "alpha secret question"})
        b"".join(response.streaming_content)
        row_a = ChatMessage.objects.get(role="user")
        response = b.post(reverse("chat_send"), {"message": "beta other question"})
        b"".join(response.streaming_content)
        row_b = ChatMessage.objects.exclude(pk=row_a.pk).get(role="user")
        self.assertTrue(row_a.session_key)
        self.assertNotEqual(row_a.session_key, row_b.session_key)

    def test_anonymous_messages_keyed_to_session(self):
        client = self.app_client()
        response = client.post(reverse("chat_send"), {"message": "hello"})
        b"".join(response.streaming_content)
        key = client.session.session_key
        self.assertTrue(key)
        self.assertTrue(ChatMessage.objects.filter(session_key=key).exists())
        self.assertFalse(ChatMessage.objects.filter(session_key="").exists())

    def test_journey_messages_keep_empty_session_key(self):
        client = self.app_client()
        self.start_journey(client)
        response = client.post(reverse("chat_send"), {"message": "hello"})
        b"".join(response.streaming_content)
        self.assertTrue(ChatMessage.objects.filter(session_key="").exists())
        self.assertFalse(ChatMessage.objects.filter(session_key=client.session.session_key).exists())


class DemoReplyTests(ChatBaseTests):
    def start_journey(self, client, number="BG147"):
        flight = Flight.objects.get(number=number)
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))

    def test_next_action_reply_bangla(self):
        client = self.app_client(lang="bn")
        self.start_journey(client)
        response = client.post(reverse("chat_send"), {"message": "এখন আমি কী করব?"})
        events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("চেক-ইন কাউন্টারে যান", text)
        self.assertTrue(events[-1]["done"])

    def test_gate_pending_reply(self):
        client = self.app_client(lang="bn")
        self.start_journey(client, "BG147")
        response = client.post(reverse("chat_send"), {"message": "আমার গেট কোথায়?"})
        events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("ঘোষণা হয়নি", text)

    def test_gate_assigned_reply(self):
        client = self.app_client()
        self.start_journey(client, "EK585")
        response = client.post(reverse("chat_send"), {"message": "Where is my gate?"})
        events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("8", text)

    def test_messages_saved_with_demo_source(self):
        client = self.app_client()
        self.start_journey(client)
        response = client.post(reverse("chat_send"), {"message": "What should I do now?"})
        b"".join(response.streaming_content)
        self.assertEqual(ChatMessage.objects.filter(role="user").count(), 1)
        assistant = ChatMessage.objects.get(role="assistant")
        self.assertEqual(assistant.source, "demo")
        self.assertIn("check-in", assistant.content.lower())

    def test_empty_message_rejected(self):
        client = self.app_client()
        response = client.post(reverse("chat_send"), {"message": "   "})
        self.assertEqual(response.status_code, 400)

    def test_history_saved_in_background(self):
        client = self.app_client()
        self.start_journey(client)
        response = client.post(reverse("chat_send"), {"message": "hello"})
        b"".join(response.streaming_content)
        self.assertTrue(ChatMessage.objects.filter(role="user", content="hello").exists())
        self.assertTrue(ChatMessage.objects.filter(role="assistant").exists())
