from datetime import datetime, time, timezone as dt_timezone

from django.test import TestCase

from apps.core.i18n import translate
from apps.core.templatetags.ui_extras import duration_label
from apps.core.times import format_clock


class HealthTests(TestCase):
    def test_health_reports_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "db": True})


class FormatClockTests(TestCase):
    def test_english_12_hour(self):
        self.assertEqual(format_clock(time(19, 30), "en"), "7:30 PM")
        self.assertEqual(format_clock(time(8, 45), "en"), "8:45 AM")
        self.assertEqual(format_clock(time(12, 0), "en"), "12:00 PM")
        self.assertEqual(format_clock(time(0, 15), "en"), "12:15 AM")
        self.assertEqual(format_clock(time(13, 5), "en"), "1:05 PM")

    def test_bangla_periods(self):
        self.assertEqual(format_clock(time(8, 45), "bn"), "সকাল 8:45")
        self.assertEqual(format_clock(time(5, 30), "bn"), "সকাল 5:30")
        self.assertEqual(format_clock(time(12, 5), "bn"), "দুপুর 12:05")
        self.assertEqual(format_clock(time(15, 59), "bn"), "দুপুর 3:59")
        self.assertEqual(format_clock(time(17, 10), "bn"), "বিকাল 5:10")
        self.assertEqual(format_clock(time(19, 30), "bn"), "সন্ধ্যা 7:30")
        self.assertEqual(format_clock(time(21, 15), "bn"), "রাত 9:15")
        self.assertEqual(format_clock(time(1, 15), "bn"), "রাত 1:15")
        self.assertEqual(format_clock(time(0, 5), "bn"), "রাত 12:05")

    def test_aware_datetime_localized_to_dhaka(self):
        value = datetime(2026, 10, 10, 13, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(format_clock(value, "en"), "7:30 PM")
        self.assertEqual(format_clock(value, "bn"), "সন্ধ্যা 7:30")
