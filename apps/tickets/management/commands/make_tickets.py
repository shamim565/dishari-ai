import random
from pathlib import Path

import qrcode
from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from apps.flights.models import Flight
from apps.journeys.services import todays_flights
from apps.tickets.ticketdata import ticket_data

FONT_CANDIDATES = {
    "regular": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}

NAVY = (10, 15, 30)
AMBER = (245, 158, 11)
AMBER_DARK = (180, 83, 9)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
LINE = (226, 232, 240)
FAINT = (248, 250, 252)

WIDTH = 1240
HEIGHT = 1040


def get_font(size, bold=False):
    for path in FONT_CANDIDATES["bold" if bold else "regular"]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default(size=size)


def draw_barcode(draw, x, y, width, height, seed):
    rng = random.Random(seed)
    cursor = x
    while cursor < x + width:
        bar = rng.choice([2, 3, 4, 6, 8])
        draw.rectangle([cursor, y, cursor + bar - 1, y + height], fill=INK)
        cursor += bar + rng.choice([2, 3, 4, 5])


def build_qr(data, size=104):
    qr = qrcode.QRCode(border=1, box_size=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0A0F1E", back_color="#FFFFFF").get_image().convert("RGB")
    return image.resize((size, size), Image.NEAREST)


def format_money(amount):
    return f"BDT {amount:,}"


def format_duration(minutes):
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}m"


class Command(BaseCommand):
    help = "Generate demo ticket images (one per seeded flight) for scan testing."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit number of tickets generated")

    def handle(self, *args, **options):
        out_dir = Path(settings.BASE_DIR) / "demo_assets" / "tickets"
        out_dir.mkdir(parents=True, exist_ok=True)

        flights = list(todays_flights())
        if options["limit"]:
            flights = flights[: options["limit"]]
        if not flights:
            self.stderr.write("No flights found for today. Run: manage.py seed_demo")
            return

        for index, flight in enumerate(flights):
            path = out_dir / f"{flight.number}_{flight.destination.code}.png"
            image = self.render_ticket(flight, index)
            image.save(path)
            self.stdout.write(f"ticket written: {path}")

        self.stdout.write(self.style.SUCCESS(f"{len(flights)} demo tickets in {out_dir}"))

    def render_ticket(self, flight: Flight, index):
        data = ticket_data(flight, index)
        img = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # ---------- header ----------
        draw.rectangle([0, 0, WIDTH, 130], fill=NAVY)
        draw.rectangle([0, 130, WIDTH, 136], fill=AMBER)
        draw.text((56, 34), flight.airline.name.upper(), font=get_font(34, bold=True), fill=(255, 255, 255))
        draw.text((56, 86), "ELECTRONIC TICKET — ITINERARY RECEIPT", font=get_font(19), fill=(203, 213, 225))
        draw.text((870, 36), "e-TICKET", font=get_font(34, bold=True), fill=AMBER)
        draw.text((870, 84), data["ticket_number"], font=get_font(22, bold=True), fill=(226, 232, 240))

        # ---------- segment ----------
        draw.text((56, 168), flight.origin.code, font=get_font(72, bold=True), fill=INK)
        draw.text((56, 248), flight.origin.city.upper(), font=get_font(21), fill=MUTED)
        draw.line([320, 210, 400, 210], fill=AMBER, width=6)
        draw.polygon([(400, 195), (430, 210), (400, 225)], fill=AMBER)
        draw.text((345, 236), format_duration(flight.duration_minutes), font=get_font(17, bold=True), fill=AMBER_DARK)
        draw.text((452, 168), flight.destination.code, font=get_font(72, bold=True), fill=INK)
        draw.text((452, 248), flight.destination.city.upper(), font=get_font(21), fill=MUTED)

        arrival = flight.arrival_datetime
        draw.text((840, 166), "DEPARTURE", font=get_font(15), fill=MUTED)
        draw.text((840, 186), flight.sched_departure.strftime("%H:%M"), font=get_font(40, bold=True), fill=INK)
        draw.text((840, 238), flight.date.strftime("%d %b %Y").upper(), font=get_font(19), fill=MUTED)
