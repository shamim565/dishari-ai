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

    def test_assistant_text_free(self):
        response = Client().get(reverse("assistant"))
        self.assertNotContains(response, "chat-history")
        self.assertNotContains(response, 'class="msg')


class AssistantVoiceModeTests(TestCase):
    def test_tts_query_forces_pipeline(self):
        response = Client().get(reverse("assistant") + "?voice=tts")
        self.assertContains(response, 'window.VOICE_MODE = "tts"')

    def test_live_query_selects_live_mode(self):
        response = Client().get(reverse("assistant") + "?voice=live")
        self.assertContains(response, 'window.VOICE_MODE = "live"')
        self.assertContains(response, "live-config")

    def test_live_without_key_falls_back_to_tts(self):
        with patch("apps.portal.views.live_api.live_configured", return_value=False):
            response = Client().get(reverse("assistant") + "?voice=live")
        self.assertContains(response, 'window.VOICE_MODE = "tts"')


class SessionEndTests(TestCase):
    def test_session_end_flushes_and_returns_home(self):
        client = Client()
        session = client.session
        session["journey_token"] = "abc123"
        session["lang"] = "en"
        session.save()
        response = client.post(reverse("session_end"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home"))
        self.assertIsNone(client.session.get("journey_token"))
        self.assertIsNone(client.session.get("lang"))

    def test_session_end_requires_post(self):
        response = Client().get(reverse("session_end"))
        self.assertEqual(response.status_code, 405)
