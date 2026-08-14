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

    def test_navigate_from_entry_without_position(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=navigate&to=IMM")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "showing the route from the entrance")
        self.assertContains(response, "Walk straight through the entrance")
        self.assertContains(response, "Departure immigration")

    def test_navigate_checkin_target_uses_flight_block(self):
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        response = client.get(reverse("home") + "?view=navigate&to=checkin")
        self.assertContains(response, "Check-in Block A")
        self.assertContains(response, "Block A")

    def test_navigate_gate_pending_notice(self):
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        response = client.get(reverse("home") + "?view=navigate&to=gate")
        self.assertContains(response, "gate has not been announced")

    def test_navigate_gate_with_assigned_gate(self):
        client = self.app_client()
        flight = Flight.objects.get(number="EK585")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        response = client.get(reverse("home") + "?view=navigate&to=gate")
        self.assertContains(response, "Gate 8")

    def test_lost_without_position_shows_hint(self):
        client = self.app_client()
        response = client.get(reverse("home") + "?view=lost")
        self.assertContains(response, "Scan a column or block QR code")

    def test_lost_with_position_shows_first_step(self):
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        client.get(reverse("scan_marker", args=["A01"]))
        response = client.get(reverse("home") + "?view=lost")
        self.assertContains(response, "Step 1 /")
        response = client.get(reverse("home") + "?view=lost&step=99")
        self.assertContains(response, "You have arrived!")

    def test_dashboard_links_to_checkin_route(self):
        client = self.app_client()
        flight = Flight.objects.get(number="BG147")
        client.post(reverse("ticket_demo_pick", args=[flight.pk]))
        response = client.get(reverse("home"))
        self.assertContains(response, "/?view=navigate")
