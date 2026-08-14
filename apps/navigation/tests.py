from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.flights.models import Flight
from apps.journeys.models import JourneySession
from apps.navigation.engine import find_route, refresh_location_index
from apps.navigation.models import Location, RouteSegment


class NavigationSeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_nav")

    def test_seed_counts(self):
        self.assertEqual(Location.objects.count(), 19)
        self.assertEqual(RouteSegment.objects.count(), 19)
        self.assertEqual(Location.objects.exclude(qr_code=None).count(), 8)

    def test_route_entry_to_block_a(self):
        refresh_location_index()
        route = find_route(Location.objects.get(code="ENTRY"), Location.objects.get(code="BLK_A"))
        self.assertEqual(len(route.steps), 2)
        self.assertEqual(route.distance_m, 125)
        self.assertIn("চেক-ইন", route.steps[0].instruction_bn)
        self.assertIn("270,126", route.points)

    def test_route_entry_to_gate8_passes_immigration_security(self):
        refresh_location_index()
        route = find_route(Location.objects.get(code="ENTRY"), Location.objects.get(code="GATE8"))
        codes = [step.to_code for step in route.steps]
        self.assertEqual(codes, ["BLK_B", "IMM", "SEC", "AIR", "GATE8"])
        self.assertEqual(route.distance_m, 435)
        self.assertEqual(route.walk_minutes, 7)

    def test_route_same_location(self):
        refresh_location_index()
        loc = Location.objects.get(code="IMM")
        route = find_route(loc, loc)
        self.assertEqual(route.steps, [])
        self.assertEqual(route.distance_m, 0)


class NavigationFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        call_command("seed_nav")

    def app_client(self):
        client = Client()
        session = client.session
        session["lang"] = "en"
        session.save()
        return client

    def test_map_panel_renders_with_markers(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=map")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "terminal-map")
        self.assertContains(response, "Immigration")
        self.assertContains(response, "Food court")

    def test_scan_qr_sets_location(self):
        client = self.app_client()
        response = client.get(reverse("scan_marker", args=["A10"]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("view=map", response["Location"])
        self.assertIn("scanned=BLK_A", response["Location"])
        self.assertEqual(client.session["location_code"], "BLK_A")
        response = client.get(reverse("home") + "?view=map")
        self.assertContains(response, "Check-in Block A")

    def test_scan_unknown_qr_redirects_to_map(self):
        client = self.app_client()
        response = client.get(reverse("scan_marker", args=["ZZZ"]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("view=map", response["Location"])
        self.assertIn("unknown=ZZZ", response["Location"])
