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


class LlmStreamTests(ChatBaseTests):
    def test_llm_path_streams_and_saves(self):
        client = self.app_client()
        fake_setup = {"provider": "gemini", "model": "gemini-2.5-flash"}

        def fake_stream(setup, messages):
            self.assertIn("NEVER invent", messages[0]["content"])
            yield "হ্যালো "
            yield "বন্ধু!"

        with (
            patch("apps.chat.views.registry.chat_setup", return_value=fake_setup),
            patch("apps.chat.views._llm_stream", side_effect=fake_stream),
        ):
            response = client.post(reverse("chat_send"), {"message": "Hi"})
            events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertEqual(text, "হ্যালো বন্ধু!")
        assistant = ChatMessage.objects.get(role="assistant")
        self.assertEqual(assistant.source, "llm")
        self.assertEqual(assistant.content, "হ্যালো বন্ধু!")

    def test_llm_error_falls_back_to_apology(self):
        client = self.app_client()
        fake_setup = {"provider": "gemini", "model": "gemini-2.5-flash"}

        def broken_stream(setup, messages):
            raise RuntimeError("boom")
            yield ""

        with (
            patch("apps.chat.views.registry.chat_setup", return_value=fake_setup),
            patch("apps.chat.views._llm_stream", side_effect=broken_stream),
        ):
            response = client.post(reverse("chat_send"), {"message": "Hi"})
            events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("Sorry", text)
        assistant = ChatMessage.objects.get(role="assistant")
        self.assertEqual(assistant.source, "demo")


class EmergencyTests(ChatBaseTests):
    def test_medical_emergency_bypasses_llm(self):
        client = self.app_client(lang="bn")
        fake_setup = {"provider": "gemini", "model": "gemini-2.5-flash"}
        with (
            patch("apps.chat.views.registry.chat_setup", return_value=fake_setup),
            patch("apps.chat.views._llm_stream") as llm,
        ):
            response = client.post(reverse("chat_send"), {"message": "আমি অসুস্থ, দরকার"})
            events = parse_sse(b"".join(response.streaming_content))
        llm.assert_not_called()
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("মেডিকেল", text)
        cards = [e["emergency"] for e in events if "emergency" in e]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["target"], "MED")

    def test_documents_emergency(self):
        client = self.app_client(lang="bn")
        response = client.post(reverse("chat_send"), {"message": "আমার পাসপোর্ট হারিয়ে গেছে"})
        events = parse_sse(b"".join(response.streaming_content))
        cards = [e["emergency"] for e in events if "emergency" in e]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["target"], "POLICE")

    def test_child_emergency(self):
        client = self.app_client()
        response = client.post(reverse("chat_send"), {"message": "I can't find my child"})
        events = parse_sse(b"".join(response.streaming_content))
        cards = [e["emergency"] for e in events if "emergency" in e]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["target"], "INFO")

    def test_handoff_event_on_unknown_question(self):
        client = self.app_client()
        response = client.post(reverse("chat_send"), {"message": "xyzzyzz blorp"})
        events = parse_sse(b"".join(response.streaming_content))
        handoffs = [e["handoff"] for e in events if "handoff" in e]
        self.assertEqual(len(handoffs), 1)
        self.assertEqual(handoffs[0]["target"], "INFO")

    def test_transit_intent(self):
        client = self.app_client(lang="bn")
        response = client.post(reverse("chat_send"), {"message": "আমার কানেক্টিং ফ্লাইট আছে"})
        events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("Transfers", text)

    def test_arrival_intent(self):
        client = self.app_client()
        response = client.post(reverse("chat_send"), {"message": "What happens after landing?"})
        events = parse_sse(b"".join(response.streaming_content))
        text = "".join(e.get("delta", "") for e in events)
        self.assertIn("baggage claim", text)


class LiveLogTests(ChatBaseTests):
    def test_live_log_stores_messages(self):
        client = self.app_client()
        response = client.post(
            reverse("chat_live_log"),
            {"input": "আমার গেট কোথায়?", "output": "আপনার গেট ১২ নম্বর।"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatMessage.objects.filter(source="live").count(), 2)

    def test_live_log_emergency_event(self):
        client = self.app_client()
        response = client.post(reverse("chat_live_log"), {"input": "আমি অসুস্থ", "output": ""})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("event", payload)
        self.assertEqual(payload["event"]["emergency"]["code"], "medical")

    def test_live_log_empty_returns_400(self):
        client = self.app_client()
        response = client.post(reverse("chat_live_log"), {"input": "", "output": ""})
        self.assertEqual(response.status_code, 400)
