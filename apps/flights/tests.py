from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.flights.models import Flight


class ArrivalComputationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_arrival_within_same_day(self):
        flight = Flight.objects.get(number="BG001")
        flight.sched_departure = time(9, 55)
        self.assertEqual(flight.duration_minutes, 700)
        self.assertEqual(flight.arrival_time, time(21, 35))
        self.assertFalse(flight.arrives_next_day)

    def test_arrival_next_day_rollover(self):
        flight = Flight.objects.get(number="BG147")
        flight.sched_departure = time(19, 30)
        self.assertEqual(flight.arrival_time, time(0, 25))
        self.assertTrue(flight.arrives_next_day)

    def test_delayed_flight_uses_effective_departure(self):
        flight = Flight.objects.get(number="BG035")
        flight.est_departure = time(2, 0)
        flight.save(update_fields=["est_departure"])
        self.assertEqual(flight.arrival_time, time(8, 15))


class EffectiveStatusTests(TestCase):
    NOW = timezone.make_aware(datetime(2026, 1, 1, 12, 0))

    def make(self, minutes, status=Flight.STATUS_SCHEDULED, est_minutes=None):
        dep = self.NOW + timedelta(minutes=minutes)
        est = self.NOW + timedelta(minutes=est_minutes) if est_minutes is not None else None
        return Flight(
            date=dep.date(),
            sched_departure=dep.time(),
            est_departure=est.time() if est else None,
            status=status,
        )

    def test_time_windows(self):
        cases = [
            (240, Flight.STATUS_SCHEDULED),
            (120, Flight.STATUS_CHECK_IN_OPEN),
            (50, Flight.STATUS_CHECK_IN_CLOSED),
            (30, Flight.STATUS_BOARDING),
            (10, Flight.STATUS_FINAL_CALL),
            (-5, Flight.STATUS_GATE_CLOSED),
            (-30, Flight.STATUS_DEPARTED),
        ]
        for minutes, expected in cases:
            with self.subTest(minutes=minutes):
                self.assertEqual(self.make(minutes).effective_status(self.NOW), expected)

    def test_grace_window_before_departed(self):
        self.assertEqual(self.make(-10).effective_status(self.NOW), Flight.STATUS_GATE_CLOSED)

    def test_cancelled_always_wins(self):
        flight = self.make(240, status=Flight.STATUS_CANCELLED)
        self.assertEqual(flight.effective_status(self.NOW), Flight.STATUS_CANCELLED)

    def test_delayed_uses_estimated_departure(self):
        flight = self.make(60, status=Flight.STATUS_DELAYED, est_minutes=120)
        self.assertEqual(flight.effective_status(self.NOW), Flight.STATUS_CHECK_IN_OPEN)

    def test_manual_status_advances_early(self):
        flight = self.make(300, status=Flight.STATUS_BOARDING)
        self.assertEqual(flight.effective_status(self.NOW), Flight.STATUS_BOARDING)

    def test_clock_supersedes_stale_status(self):
        flight = self.make(-300, status=Flight.STATUS_BOARDING)
        self.assertEqual(flight.effective_status(self.NOW), Flight.STATUS_DEPARTED)

    def test_display_status_keeps_delayed_badge(self):
        flight = self.make(120, status=Flight.STATUS_DELAYED, est_minutes=120)
        self.assertEqual(flight.display_status(self.NOW), Flight.STATUS_DELAYED)

    def test_display_status_terminal_wins_over_delayed(self):
        flight = self.make(-300, status=Flight.STATUS_DELAYED, est_minutes=-300)
        self.assertEqual(flight.display_status(self.NOW), Flight.STATUS_DEPARTED)
