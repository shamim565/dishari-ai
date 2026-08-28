from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.times import format_clock
from apps.flights.models import Flight
from apps.journeys.models import JourneySession
from apps.notifications.engine import create_event
from apps.notifications.models import FlightEvent


class EventEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_check_in_open_event(self):
        flight = Flight.objects.get(number="BG147")
        event = create_event(flight, FlightEvent.KIND_CHECK_IN_OPEN)
        flight.refresh_from_db()
        self.assertTrue(flight.checkin_open)
        self.assertEqual(flight.status, Flight.STATUS_CHECK_IN_OPEN)
        self.assertEqual(event.priority, FlightEvent.PRIORITY_NORMAL)
        self.assertIn("17-20", event.message_bn)
        self.assertIn("Check-in has started", event.message_en)

    def test_gate_change_event_is_urgent(self):
        flight = Flight.objects.get(number="BG147")
        event = create_event(flight, FlightEvent.KIND_GATE_CHANGE, gate="12")
        flight.refresh_from_db()
        self.assertEqual(flight.gate, "12")
        self.assertEqual(event.priority, FlightEvent.PRIORITY_URGENT)
        self.assertIn("12", event.message_bn)
        self.assertIn("Important", event.message_en)

    def test_delay_event_updates_est_time(self):
        flight = Flight.objects.get(number="BG147")
        base = datetime.combine(flight.date, flight.sched_departure)
        event = create_event(flight, FlightEvent.KIND_DELAY, delay_minutes=60)
        flight.refresh_from_db()
        expected = (base + timedelta(minutes=60)).time()
        self.assertEqual(flight.status, Flight.STATUS_DELAYED)
        self.assertEqual(flight.est_departure, expected)
        self.assertIn("1 ঘণ্টা", event.message_bn)
        self.assertIn(format_clock(expected, "bn"), event.message_bn)
        self.assertIn(format_clock(expected, "en"), event.message_en)

    def test_boarding_and_cancel(self):
        flight = Flight.objects.get(number="BG147")
        create_event(flight, FlightEvent.KIND_BOARDING)
        flight.refresh_from_db()
        self.assertEqual(flight.status, Flight.STATUS_BOARDING)

        event = create_event(flight, FlightEvent.KIND_CANCELLED)
        flight.refresh_from_db()
        self.assertEqual(flight.status, Flight.STATUS_CANCELLED)
        self.assertTrue(event.is_urgent)

    def test_counter_change(self):
        flight = Flight.objects.get(number="BG147")
        create_event(flight, FlightEvent.KIND_COUNTER_CHANGE, counters="23-26", block="B")
        flight.refresh_from_db()
        self.assertEqual(flight.checkin_counters, "23-26")
        self.assertEqual(flight.checkin_block, "B")


class NotificationsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def app_client(self):
        client = Client()
        session = client.session
        session["lang"] = "bn"
        session.save()
        return client

    def start_journey(self, client, number="BG147"):
        flight = Flight.objects.get(number=number)
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))

    def test_api_without_session_returns_no_events(self):
        client = Client()
        response = client.get(reverse("api_notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"], [])

    def test_peek_returns_latest(self):
        flight = Flight.objects.get(number="BG147")
        create_event(flight, FlightEvent.KIND_CHECK_IN_OPEN)
        client = self.app_client()
        response = client.get(reverse("api_notifications") + "?peek=1")
        self.assertEqual(response.json()["latest"], FlightEvent.objects.latest("id").id)

    def test_events_scoped_to_journey_flight(self):
        client = self.app_client()
        self.start_journey(client, "BG147")
        bg147 = Flight.objects.get(number="BG147")
        ek585 = Flight.objects.get(number="EK585")
        create_event(bg147, FlightEvent.KIND_CHECK_IN_OPEN)
        create_event(ek585, FlightEvent.KIND_GATE_CHANGE, gate="9")

        response = client.get(reverse("api_notifications") + "?after=0")
        events = response.json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "CHECK_IN_OPEN")
        self.assertIn("চেক-ইন", events[0]["message"])

    def test_after_param_filters(self):
        client = self.app_client()
        self.start_journey(client)
        flight = Flight.objects.get(number="BG147")
        first = create_event(flight, FlightEvent.KIND_CHECK_IN_OPEN)
        create_event(flight, FlightEvent.KIND_BOARDING)
        response = client.get(reverse("api_notifications") + f"?after={first.id}")
        events = response.json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "BOARDING")


class NotificationsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def app_client(self):
        client = Client()
        session = client.session
        session["lang"] = "bn"
        session.save()
        return client

    def test_page_without_journey(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=notifications")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "বিজ্ঞপ্তি")

    def test_page_with_event(self):
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        create_event(flight, FlightEvent.KIND_GATE_CHANGE, gate="12")
        response = client.get(reverse("home") + "?view=notifications")
        self.assertContains(response, "গুরুত্বপূর্ণ")
        self.assertContains(response, "12")


class OpsPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_panel_requires_pin(self):
        client = Client()
        response = client.get(reverse("ops_panel"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("ops_login"))

    def test_wrong_pin_rejected(self):
        client = Client()
        response = client.post(reverse("ops_login"), {"pin": "0000"})
        self.assertContains(response, "Wrong PIN")

    def test_pin_unlocks_and_action_works(self):
        client = Client()
        response = client.post(reverse("ops_login"), {"pin": "1234"})
        self.assertEqual(response.status_code, 302)

        flight = Flight.objects.get(number="BG147")
        response = client.post(reverse("ops_action", args=[flight.pk, "gate-change"]), {"gate": "12"})
        self.assertEqual(response.status_code, 302)

        flight.refresh_from_db()
        self.assertEqual(flight.gate, "12")
        event = FlightEvent.objects.latest("id")
        self.assertEqual(event.kind, FlightEvent.KIND_GATE_CHANGE)
        self.assertTrue(event.is_urgent)

    def test_action_requires_unlock(self):
        client = Client()
        flight = Flight.objects.get(number="BG147")
        response = client.post(reverse("ops_action", args=[flight.pk, "boarding"]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("ops_login"))

    def test_panel_renders_with_flights(self):
        client = Client()
        client.post(reverse("ops_login"), {"pin": "1234"})
        response = client.get(reverse("ops_panel"))
        self.assertContains(response, "BG147")
        self.assertContains(response, "Check-in open")
        self.assertContains(response, "Passenger intelligence")

    def test_panel_shows_question_topics(self):
        from apps.chat.models import ChatMessage

        ChatMessage.objects.create(role="user", content="আমার গেট কোথায়?", lang="bn", source="demo")
        ChatMessage.objects.create(role="user", content="Where is my gate?", lang="en", source="demo")
        client = Client()
        client.post(reverse("ops_login"), {"pin": "1234"})
        response = client.get(reverse("ops_panel"))
        self.assertContains(response, "Gate")

    def test_reset_reseeds_data(self):
        client = Client()
        client.post(reverse("ops_login"), {"pin": "1234"})
        JourneySession.objects.create(
            passenger_name="X", flight=Flight.objects.get(number="BG147"), source="demo"
        )
        response = client.post(reverse("ops_reset"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(JourneySession.objects.count(), 0)
        self.assertEqual(Flight.objects.count(), 8)