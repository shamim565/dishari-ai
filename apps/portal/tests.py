from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch


class DashboardTests(TestCase):
    def test_dashboard_renders_without_any_session(self):
        response = Client().get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "assistant-frame")
        self.assertContains(response, "/assistant/")
        self.assertContains(response, "?view=journey")

    def test_language_toggle_switches_dashboard(self):
        client = Client()
        response = client.get(reverse("set_lang", args=["en"]) + "?next=/")
        self.assertEqual(response.status_code, 302)
        response = client.get(reverse("assistant"))
        self.assertContains(response, "Tap the mic to start")

    def test_dashboard_panel_defaults_to_ticket(self):
        response = Client().get(reverse("home"))
        self.assertContains(response, "স্ক্যান করুন")
        self.assertContains(response, "data:image/png;base64")
        self.assertContains(response, "ticket-hold")

    def test_kiosk_instrumentation_always_present(self):
        response = Client().get(reverse("home"))
        self.assertContains(response, "KIOSK_CONFIG")
        self.assertContains(response, "kiosk-idle-overlay")
        self.assertContains(response, "kiosk.js")

    def test_removed_routes_are_gone(self):
        client = Client()
        for path in ("/portal/", "/portal/connect/", "/welcome/", "/kiosk/", "/ask/", "/soon/ticket/", "/journey/"):
            self.assertEqual(client.get(path).status_code, 404, path)


class AssistantPageTests(TestCase):
    def test_assistant_page_serves_voice_panel(self):
        response = Client().get(reverse("assistant"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "voice-mic")
        self.assertContains(response, "chat-config")
        self.assertContains(response, "মাইকে ট্যাপ করুন")
