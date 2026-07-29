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
