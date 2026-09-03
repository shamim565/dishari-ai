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

        draw.text((1052, 166), "ARRIVAL", font=get_font(15), fill=MUTED)
        if arrival:
            draw.text((1052, 186), arrival.strftime("%H:%M"), font=get_font(40, bold=True), fill=INK)
            if flight.arrives_next_day:
                draw.text((1196, 196), "+1", font=get_font(20, bold=True), fill=AMBER_DARK)
            draw.text((1052, 238), arrival.strftime("%d %b %Y").upper(), font=get_font(19), fill=MUTED)
        else:
            draw.text((1052, 186), "—", font=get_font(40, bold=True), fill=INK)

        draw.line([56, 296, WIDTH - 56, 296], fill=LINE, width=2)

        # ---------- details grid ----------
        boarding = flight.sched_departure.replace(hour=(flight.sched_departure.hour - 1) % 24)
        columns = [
            [
                ("PASSENGER", f"{data['title']} {data['name_print']}"),
                ("PASSENGER TYPE", data["passenger_type"]),
                ("SEAT", data["seat"]),
                ("CLASS", data["cabin"]),
            ],
            [
                ("FLIGHT NUMBER", flight.number),
                ("TERMINAL", flight.terminal or "TERMINAL 2"),
                ("BOARDING TIME", boarding.strftime("%H:%M")),
                ("GATE", flight.gate or "TBA"),
            ],
            [
                ("BOOKING REFERENCE (PNR)", data["pnr"]),
                ("E-TICKET NUMBER", data["ticket_number"]),
                ("CHECK-IN COUNTERS", flight.checkin_counters or "TBA"),
                ("BAGGAGE ALLOWANCE", data["baggage"]),
            ],
        ]
        column_x = [56, 470, 850]
        row_y = [330, 424, 518, 612]
        for x, column in zip(column_x, columns):
            for y, (label, value) in zip(row_y, column):
                draw.text((x, y), label, font=get_font(15), fill=MUTED)
                draw.text((x, y + 21), value, font=get_font(23, bold=True), fill=INK)

        # ---------- fare ----------
        draw.rounded_rectangle([56, 706, WIDTH - 56, 806], radius=14, fill=FAINT, outline=LINE, width=2)
        fare_columns = [
            ("FARE BASIS", data["fare_basis"]),
            ("FARE", format_money(data["fare"])),
            ("TAXES & FEES", format_money(data["taxes"])),
            ("TOTAL", format_money(data["total"])),
        ]
        fare_x = [86, 360, 640, 930]
        for x, (label, value) in zip(fare_x, fare_columns):
            draw.text((x, 728), label, font=get_font(15), fill=MUTED)
            draw.text((x, 754), value, font=get_font(25, bold=True), fill=INK)

        draw.text(
            (56, 826),
            f"ISSUED {data['issue_date'].strftime('%d %b %Y').upper()}  ·  AGENT: {data['agent']}  ·  FORM OF PAYMENT: {data['form_of_payment']}",
            font=get_font(17),
            fill=MUTED,
        )

        draw.line([56, 872, WIDTH - 56, 872], fill=LINE, width=2)

        # ---------- footer ----------
        draw_barcode(draw, 56, 896, 540, 46, seed=flight.number)
        qr = build_qr(
            f"BCBP|{flight.airline.code}|{flight.number}|{flight.date.strftime('%d%b%y').upper()}|"
            f"{flight.origin.code}{flight.destination.code}|{data['name_print']}|{data['seat']}|{data['pnr']}"
        )
        img.paste(qr, (640, 890))
        draw.text((766, 898), "BOOKING REF (PNR)", font=get_font(15), fill=MUTED)
        draw.text((766, 920), data["pnr"], font=get_font(30, bold=True), fill=INK)
        draw.text((766, 962), f"FLIGHT {flight.number}  ·  SEAT {data['seat']}", font=get_font(17), fill=MUTED)
        draw.text(
            (56, 972),
            "DEMO DOCUMENT — NOT VALID FOR TRAVEL",
            font=get_font(17, bold=True),
            fill=AMBER_DARK,
        )

        return img
