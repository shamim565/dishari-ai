from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import ChatMessage
from apps.flights.models import Flight
from apps.journeys import engine
from apps.journeys.models import JourneySession
from apps.journeys.services import create_journey
from apps.tickets.services import match_flight


class JourneyEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        call_command("seed_demo")

    def make_journey(self, number="BG147", stage=JourneySession.STAGE_ENTERED):
        flight = Flight.objects.get(number=number)
        journey = create_journey(flight=flight, passenger_name="Test Passenger", source="demo")
        journey.stage = stage
        journey.save(update_fields=["stage"])
        return journey

    def test_timeline_progression(self):
        journey = self.make_journey(stage=JourneySession.STAGE_ENTERED)
        states = [item["state"] for item in engine.timeline(journey)]
        self.assertEqual(states[0], "current")
        self.assertEqual(states[1:], ["upcoming"] * 5)

        journey.stage = JourneySession.STAGE_IMMIGRATION
        journey.save(update_fields=["stage"])
        states = [item["state"] for item in engine.timeline(journey)]
        self.assertEqual(states[:2], ["done", "done"])
        self.assertEqual(states[2], "current")

    def test_timeline_all_done_when_boarded(self):
        journey = self.make_journey(stage=JourneySession.STAGE_BOARDED)
        states = {item["state"] for item in engine.timeline(journey)}
        self.assertEqual(states, {"done"})

    def test_next_action_per_stage(self):
        journey = self.make_journey(stage=JourneySession.STAGE_ENTERED)
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_entered_title")

        journey.stage = JourneySession.STAGE_IMMIGRATION
        self.assertEqual(engine.next_action(journey)["title_key"], "task_security_title")

        journey.stage = JourneySession.STAGE_GATE
        self.assertEqual(engine.next_action(journey)["title_key"], "task_gate_wait_title")

        journey.flight.status = Flight.STATUS_BOARDING
        journey.flight.save(update_fields=["status"])
        self.assertEqual(engine.next_action(journey)["title_key"], "task_boarding_title")

    def test_checkin_not_open_shows_wait_warning(self):
        journey = self.make_journey(number="BG147")
        action = engine.next_action(journey)
        self.assertEqual(action["warning_key"], "task_checkin_wait")

        journey.flight.checkin_open = True
        journey.flight.save(update_fields=["checkin_open"])
        self.assertIsNone(engine.next_action(journey)["warning_key"])

    def test_departed_flight_shows_missed_action(self):
        journey = self.make_journey(number="G9518", stage=JourneySession.STAGE_ENTERED)
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_departed_title")
        self.assertFalse(action["advance_allowed"])
        self.assertEqual(action["nav_target"], "INFO")

    def test_gate_closed_flight_shows_missed_action(self):
        journey = self.make_journey(number="BG001", stage=JourneySession.STAGE_AIRSIDE)
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_departed_title")
        self.assertEqual(action["nav_target"], "INFO")

    def test_cancelled_flight_shows_cancelled_action(self):
        journey = self.make_journey(number="QR641", stage=JourneySession.STAGE_CHECK_IN)
        journey.flight.status = Flight.STATUS_CANCELLED
        journey.flight.save(update_fields=["status"])
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_cancelled_title")
        self.assertFalse(action["advance_allowed"])
        self.assertEqual(action["nav_target"], "INFO")

    def test_boarded_passenger_unaffected_by_missed_flight(self):
        journey = self.make_journey(number="G9518", stage=JourneySession.STAGE_BOARDED)
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_boarded_title")
        self.assertEqual(action["state"], "done")

    def test_missed_journey_context_has_no_countdowns(self):
        from apps.chat.context import journey_context

        journey = self.make_journey(number="G9518")
        context = journey_context(journey, "en")
        self.assertNotIn("already due", context)
        self.assertIn("Scheduled departure was", context)

    def test_boarding_flight_at_checkin_stage_has_no_false_warning(self):
        journey = self.make_journey(number="EK585")
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_entered_title")
        self.assertIsNone(action["warning_key"])

    def test_clock_departed_flight_shows_missed_action(self):
        journey = self.make_journey(number="BG147")
        dep = timezone.localtime(timezone.now()) - timedelta(hours=1)
        journey.flight.date = dep.date()
        journey.flight.sched_departure = dep.time()
        journey.flight.est_departure = None
        journey.flight.save(update_fields=["date", "sched_departure", "est_departure"])
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_departed_title")
        self.assertTrue(action["missed"])

    def test_gate_stage_boarding_via_clock(self):
        journey = self.make_journey(number="BG147", stage=JourneySession.STAGE_GATE)
        dep = timezone.localtime(timezone.now()) + timedelta(minutes=30)
        journey.flight.date = dep.date()
        journey.flight.sched_departure = dep.time()
        journey.flight.est_departure = None
        journey.flight.save(update_fields=["date", "sched_departure", "est_departure"])
        action = engine.next_action(journey)
        self.assertEqual(action["title_key"], "task_boarding_title")

    def test_countdowns_ordered(self):
        journey = self.make_journey()
        minutes = {c["key"]: c["minutes"] for c in engine.countdowns(journey)}
        self.assertLess(minutes["boarding_starts_label"], minutes["departure_label"])
        self.assertLess(minutes["leave_for_gate_label"], minutes["boarding_starts_label"])

    def test_advance_and_regress(self):
        journey = self.make_journey()
        engine.advance(journey)
        self.assertEqual(journey.stage, JourneySession.STAGE_CHECK_IN)

        for _ in range(10):
            engine.advance(journey)
        self.assertEqual(journey.stage, JourneySession.STAGE_BOARDED)

        engine.regress(journey)
        self.assertEqual(journey.stage, JourneySession.STAGE_GATE)

        for _ in range(10):
            engine.regress(journey)
        self.assertEqual(journey.stage, JourneySession.STAGE_ENTERED)


class DashboardFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def app_client(self):
        client = Client()
        session = client.session
        session["lang"] = "en"
        session.save()
        return client

    def start_journey(self, client, number="BG147"):
        flight = Flight.objects.get(number=number)
        return client.post(reverse("ticket_demo_pick", args=[flight.pk]))

    def test_journey_page_removed(self):
        response = self.app_client().get("/journey/")
        self.assertEqual(response.status_code, 404)

    def test_home_shows_journey_panel_when_active(self):
        client = self.app_client()
        self.start_journey(client)
        response = client.get(reverse("home"))
        self.assertContains(response, "Go to the check-in counter")
        self.assertContains(response, "Journey steps")

    def test_missed_flight_panel_shows_factual_departure(self):
        client = self.app_client()
        session = client.session
        session["lang"] = "bn"
        session.save()
        self.start_journey(client, number="G9518")
        response = client.get(reverse("home"))
        html = response.content.decode()
        self.assertIn("ফ্লাইট ছেড়ে গেছে", html)
        self.assertIn("ছাড়ার সময়", html)
        self.assertNotIn("এখনই", html)

    def test_full_stage_walkthrough(self):
        client = self.app_client()
        self.start_journey(client)

        response = client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Go to the check-in counter")
        self.assertContains(response, "17-20")

        for expected in (
            "Go to departure immigration",
            "Clear security screening",
            "Proceed airside towards your gate",
            "Go to your boarding gate",
            "Wait at the gate",
            "Boarded",
        ):
            client.post(reverse("journey_advance"))
            response = client.get(reverse("home"))
            self.assertContains(response, expected)

        journey = JourneySession.objects.get()
        self.assertEqual(journey.stage, JourneySession.STAGE_BOARDED)

    def test_regress_from_dashboard(self):
        client = self.app_client()
        self.start_journey(client)
        client.post(reverse("journey_advance"))
        client.post(reverse("journey_advance"))
        client.post(reverse("journey_regress"))
        journey = JourneySession.objects.get()
        self.assertEqual(journey.stage, JourneySession.STAGE_CHECK_IN)

    def test_dashboard_bangla(self):
        client = self.app_client()
        session = client.session
        session["lang"] = "bn"
        session.save()
        self.start_journey(client)
        response = client.get(reverse("home"))
        self.assertContains(response, "চেক-ইন কাউন্টারে যান")
        self.assertContains(response, "যাত্রার ধাপ")

    def test_verified_continue_links_to_home(self):
        client = self.app_client()
        self.start_journey(client)
        response = client.get(reverse("ticket_verified"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("home"), response["Location"])


class ArrivalGuideTests(TestCase):
    def app_client(self, lang="en"):
        client = Client()
        session = client.session
        session["lang"] = lang
        session.save()
        return client

    def test_arrival_page_english(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=arrival")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transit &amp; Arrival Guide")
        self.assertContains(response, "Baggage claim")

    def test_arrival_page_bangla(self):
        client = self.app_client(lang="bn")
        response = client.get(reverse("home") + "?view=arrival")
        self.assertContains(response, "ট্রানজিট")
        self.assertContains(response, "ব্যাগেজ ক্লেইম")

    def test_boarded_dashboard_links_to_arrival(self):
        call_command("seed_demo")
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        journey = JourneySession.objects.get()
        journey.stage = JourneySession.STAGE_BOARDED
        journey.save(update_fields=["stage"])
        response = client.get(reverse("home"))
        self.assertContains(response, "/?view=arrival")


class PurgeSessionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_purge_removes_expired_journeys_and_stale_chat(self):
        flight = Flight.objects.get(number="BG147")
        old = create_journey(flight=flight, passenger_name="Old", source="demo")
        old.expires_at = timezone.now() - timedelta(hours=48)
        old.save(update_fields=["expires_at"])
        ChatMessage.objects.create(journey=old, role="user", content="old message", lang="en")

        fresh = create_journey(flight=flight, passenger_name="Fresh", source="demo")
        ChatMessage.objects.create(journey=fresh, role="user", content="fresh message", lang="en")

        anon = ChatMessage.objects.create(
            journey=None, session_key="abc123", role="user", content="anon old", lang="en"
        )
        ChatMessage.objects.filter(pk=anon.pk).update(created_at=timezone.now() - timedelta(hours=48))

        call_command("purge_sessions")

        self.assertFalse(JourneySession.objects.filter(pk=old.pk).exists())
        self.assertFalse(ChatMessage.objects.filter(content="old message").exists())
        self.assertFalse(ChatMessage.objects.filter(content="anon old").exists())
        self.assertTrue(JourneySession.objects.filter(pk=fresh.pk).exists())
        self.assertTrue(ChatMessage.objects.filter(content="fresh message").exists())