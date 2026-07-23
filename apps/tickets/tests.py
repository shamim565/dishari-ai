import io
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.core.times import format_clock
from apps.flights.models import Flight
from apps.journeys.models import JourneySession
from apps.tickets.handoff import HANDOFF_KEY
from apps.tickets.models import TicketHandoff, TicketScan
from apps.tickets.services import match_flight, normalize_flight_number

EXTRACTION = {
    "passenger_name": "Md Rahim Uddin",
    "airline_name": "Biman Bangladesh Airlines",
    "airline_code": "BG",
    "flight_number": "BG147",
    "origin_code": "DAC",
    "destination_code": "DXB",
    "date": str(timezone.localdate()),
    "departure_time": "19:30",
    "pnr": "ABC123",
    "seat": "22A",
    "cabin": "ECONOMY",
    "confidence": 0.95,
}


def make_image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), (250, 250, 250)).save(buffer, format="JPEG")
    return buffer.getvalue()


class SeededTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def app_client(self):
        client = Client()
        session = client.session
        session["lang"] = "en"
        session.save()
        return client


class DemoPickerTests(SeededTestCase):
    def test_picker_lists_all_flights(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=ticket")
        self.assertEqual(response.status_code, 200)
        numbers = [f.number for f in response.context["flights"]]
        self.assertIn("G9518", numbers)  # departed — selectable for the missed-flight demo
        self.assertIn("BG001", numbers)  # gate closed
        self.assertIn("BG147", numbers)


class FlightMatchingTests(SeededTestCase):
    def test_normalize_flight_number(self):
        self.assertEqual(normalize_flight_number("BG 147", "BG"), "BG147")
        self.assertEqual(normalize_flight_number("147", "bg"), "BG147")
        self.assertEqual(normalize_flight_number("bs-341", None), "BS341")

    def test_match_existing_flight(self):
        flight, error = match_flight(EXTRACTION)
        self.assertIsNone(error)
        self.assertEqual(flight.number, "BG147")

    def test_match_unknown_flight(self):
        data = dict(EXTRACTION, flight_number="ZZ999")
        flight, error = match_flight(data)
        self.assertIsNone(flight)
        self.assertEqual(error, "err_no_flight")

    def test_match_wrong_origin(self):
        data = dict(EXTRACTION, origin_code="DXB")
        flight, error = match_flight(data)
        self.assertIsNone(flight)
        self.assertEqual(error, "err_not_dac")


class DemoFlowTests(SeededTestCase):
    def test_demo_pick_creates_journey_and_verified_page(self):
        from apps.journeys.services import todays_flights
        from apps.tickets.ticketdata import ticket_data

        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        flights = list(todays_flights())
        index = next(i for i, f in enumerate(flights) if f.pk == flight.pk)
        expected_name = ticket_data(flight, index)["name_display"]

        response = client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home") + "?view=journey")

        self.assertEqual(JourneySession.objects.count(), 1)
        journey = JourneySession.objects.first()
        self.assertEqual(journey.flight, flight)
        self.assertEqual(journey.passenger_name, expected_name)

        response = client.get(reverse("home") + "?view=journey")
        self.assertContains(response, "BG147")
        self.assertContains(response, "Dubai")
        self.assertContains(response, format_clock(flight.effective_departure, "en"))
        self.assertContains(response, expected_name)
        self.assertContains(response, "Go to the check-in counter")

        response = client.get(reverse("home"))
        self.assertContains(response, "Go to the check-in counter")

    def test_verified_page_bangla_time_format(self):
        client = self.app_client()
        session = client.session
        session["lang"] = "bn"
        session.save()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        response = client.get(reverse("home") + "?view=journey")
        self.assertContains(response, format_clock(flight.effective_departure, "bn"))

    def test_verified_page_shows_arrival_with_next_day(self):
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        now = timezone.localtime(timezone.now())
        future = now + timedelta(minutes=5)
        if future.date() != now.date():
            self.skipTest("near midnight; next-day arrival window unavailable")
        if future.hour < 19 or (future.hour == 19 and future.minute <= 5):
            future = now.replace(hour=19, minute=10, second=0, microsecond=0)
        flight.sched_departure = future.time().replace(second=0, microsecond=0)
        flight.est_departure = None
        flight.save(update_fields=["sched_departure", "est_departure"])
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        response = client.get(reverse("home") + "?view=journey")
        self.assertContains(response, format_clock(flight.arrival_time, "en"))
        self.assertContains(response, "next day")

    def test_demo_pick_matches_generated_ticket_data(self):
        from apps.journeys.services import todays_flights
        from apps.tickets.ticketdata import ticket_data

        flight = Flight.objects.get(number="BG147")
        flights = list(todays_flights())
        index = next(i for i, f in enumerate(flights) if f.pk == flight.pk)
        data = ticket_data(flight, index)

        client = self.app_client()
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        journey = JourneySession.objects.get()
        self.assertEqual(journey.passenger_name, data["name_display"])
        self.assertEqual(journey.pnr, data["pnr"])
        self.assertEqual(journey.seat, data["seat"])

    def test_demo_picker_lists_todays_flights(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=ticket")
        self.assertContains(response, "BG147")
        self.assertContains(response, "Jeddah")
        self.assertContains(response, "demo-modal")
        self.assertContains(response, "Try demo tickets")
        self.assertContains(response, "Close demo tickets")


class UploadFlowTests(SeededTestCase):
    def test_bad_file_rejected(self):
        client = self.app_client()
        response = client.post(
            reverse("ticket_scan"),
            {"ticket_image": io.BytesIO(b"not-an-image")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("e=bad_file", response["Location"])
        self.assertTrue(TicketScan.objects.filter(error_code="bad_file").exists())

    def test_upload_without_ai_key_redirects_to_demo_advice(self):
        client = self.app_client()
        with patch("apps.tickets.views.registry.vision_available", return_value=False):
            upload = io.BytesIO(make_image_bytes())
            upload.name = "ticket.jpg"
            response = client.post(reverse("ticket_scan"), {"ticket_image": upload})
        self.assertEqual(response.status_code, 302)
        self.assertIn("view=ticket", response["Location"])
        self.assertIn("e=ai", response["Location"])
