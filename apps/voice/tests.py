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
