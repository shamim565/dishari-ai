import io
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.flights.models import Flight
from apps.journeys.services import create_journey


class VoiceEndpointTests(TestCase):
    def app_client(self):
        client = Client()
        session = client.session
        session.save()
        return client

    def test_status_without_keys(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.azure.azure_configured", return_value=False),
            patch("apps.voice.views.gemini.gemini_configured", return_value=False),
        ):
            response = client.get(reverse("voice_status"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])

    def test_tts_without_keys_returns_503(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.azure.azure_configured", return_value=False),
            patch("apps.voice.views.gemini.gemini_configured", return_value=False),
        ):
            response = client.post(reverse("voice_tts"), {"text": "স্বাগতম"})
        self.assertEqual(response.status_code, 503)

    def test_stt_without_key_returns_503(self):
        client = self.app_client()
        audio = io.BytesIO(b"RIFF0000WAVE")
        audio.name = "voice.wav"
        with patch("apps.voice.views.azure.azure_configured", return_value=False):
            response = client.post(reverse("voice_stt"), {"audio": audio})
        self.assertEqual(response.status_code, 503)

    def test_tts_with_mocked_gemini(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.tts_provider", return_value="gemini"),
            patch("apps.voice.views.gemini.gemini_configured", return_value=True),
            patch("apps.voice.views.gemini.synthesize", return_value=(b"fake-wav", "Kore")),
        ):
            response = client.post(reverse("voice_tts"), {"text": "স্বাগতম", "lang": "bn"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")
        self.assertEqual(response["X-Voice"], "Kore")
        self.assertEqual(response["X-TTS-Provider"], "gemini")
        self.assertEqual(response.content, b"fake-wav")

    def test_tts_falls_back_to_azure_when_gemini_fails(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.tts_provider", return_value="gemini"),
            patch("apps.voice.views.gemini.gemini_configured", return_value=True),
            patch("apps.voice.views.gemini.synthesize", side_effect=RuntimeError("boom")),
            patch("apps.voice.views.azure.azure_configured", return_value=True),
            patch(
                "apps.voice.views.azure.synthesize",
                return_value=(b"fake-mp3", "bn-BD-NabanitaNeural"),
            ),
        ):
            response = client.post(reverse("voice_tts"), {"text": "স্বাগতম", "lang": "bn"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        self.assertEqual(response["X-Voice"], "bn-BD-NabanitaNeural")
        self.assertEqual(response["X-TTS-Provider"], "azure")
        self.assertEqual(response.content, b"fake-mp3")

    def test_tts_with_mocked_azure(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.tts_provider", return_value="azure"),
            patch("apps.voice.views.azure.azure_configured", return_value=True),
            patch(
                "apps.voice.views.azure.synthesize",
                return_value=(b"fake-mp3", "bn-BD-NabanitaNeural"),
            ),
        ):
            response = client.post(reverse("voice_tts"), {"text": "স্বাগতম", "lang": "bn"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        self.assertEqual(response["X-Voice"], "bn-BD-NabanitaNeural")
        self.assertEqual(response.content, b"fake-mp3")

    def test_tts_empty_text(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.azure.azure_configured", return_value=True),
            patch("apps.voice.views.gemini.gemini_configured", return_value=True),
        ):
            response = client.post(reverse("voice_tts"), {"text": "  "})
        self.assertEqual(response.status_code, 400)

    def test_stt_with_mocked_azure(self):
        client = self.app_client()
        audio = io.BytesIO(b"RIFF0000WAVE")
        audio.name = "voice.wav"
        with (
            patch("apps.voice.views.azure.azure_configured", return_value=True),
            patch("apps.voice.views.azure.recognize_wav", return_value="আমার গেট কোথায়"),
        ):
            response = client.post(reverse("voice_stt"), {"audio": audio, "lang": "bn"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "আমার গেট কোথায়")

    def test_live_token_without_key_returns_503(self):
        client = self.app_client()
        with patch("apps.voice.views.live.live_configured", return_value=False):
            response = client.post(reverse("voice_live_token"))
        self.assertEqual(response.status_code, 503)

    def test_live_token_mints_and_builds_config(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.live.live_configured", return_value=True),
            patch("apps.voice.views.live.mint_token", return_value="auth_tokens/test-token"),
            patch("apps.voice.views.live.live_model", return_value="gemini-3.8-live"),
        ):
            response = client.post(reverse("voice_live_token"), {"lang": "bn"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["token"], "auth_tokens/test-token")
        self.assertEqual(data["model"], "gemini-3.8-live")
        self.assertIn("BidiGenerateContentConstrained", data["ws_url"])
        config = data["config"]
        self.assertEqual(config["generationConfig"]["responseModalities"], ["AUDIO"])
        self.assertIn("systemInstruction", config)
        self.assertIn("outputAudioTranscription", config)
        self.assertIn("ctx_hash", data)

    def test_live_context_without_journey(self):
        client = self.app_client()
        with patch("apps.voice.views.live.live_configured", return_value=True):
            response = client.get(reverse("voice_live_context"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hash"], "none")
        self.assertEqual(response.json()["context"], "")

    def test_live_context_without_key_returns_503(self):
        client = self.app_client()
        with patch("apps.voice.views.live.live_configured", return_value=False):
            response = client.get(reverse("voice_live_context"))
        self.assertEqual(response.status_code, 503)

    def test_live_token_error_returns_502(self):
        client = self.app_client()
        with (
            patch("apps.voice.views.live.live_configured", return_value=True),
            patch("apps.voice.views.live.mint_token", side_effect=RuntimeError("boom")),
        ):
            response = client.post(reverse("voice_live_token"))
        self.assertEqual(response.status_code, 502)


class LiveContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        call_command("seed_nav")

    def journey_client(self, lang="bn"):
        flight = Flight.objects.filter(date=timezone.localdate()).first()
        journey = create_journey(
            flight=flight, passenger_name="Test Passenger", source="demo", lang=lang
        )
        client = Client()
        session = client.session
        session["journey_token"] = journey.token
        session["lang"] = lang
        session.save()
        return client, journey

    def test_live_context_with_journey(self):
        client, journey = self.journey_client()
        with patch("apps.voice.views.live.live_configured", return_value=True):
            response = client.get(reverse("voice_live_context"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotEqual(data["hash"], "none")
        self.assertIn(journey.flight.number, data["context"])

    def test_live_token_includes_ctx_hash_with_journey(self):
        client, _ = self.journey_client()
        with (
            patch("apps.voice.views.live.live_configured", return_value=True),
            patch("apps.voice.views.live.mint_token", return_value="auth_tokens/test-token"),
            patch("apps.voice.views.live.live_model", return_value="gemini-3.8-live"),
        ):
            response = client.post(reverse("voice_live_token"), {"lang": "bn"})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["ctx_hash"], "none")
