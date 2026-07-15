from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.flights.models import Airline, Airport, Flight
from apps.journeys.models import JourneySession
from apps.tickets.models import TicketHandoff, TicketScan

AIRPORTS = [
    ("DAC", "Dhaka", "Hazrat Shahjalal International Airport", "ঢাকা"),
    ("DXB", "Dubai", "Dubai International Airport", "দুবাই"),
    ("JED", "Jeddah", "King Abdulaziz International Airport", "জেদ্দা"),
    ("KUL", "Kuala Lumpur", "Kuala Lumpur International Airport", "কুয়ালালামপুর"),
    ("DOH", "Doha", "Hamad International Airport", "দোহা"),
    ("SHJ", "Sharjah", "Sharjah International Airport", "শারজাহ"),
    ("LHR", "London", "Heathrow Airport", "লন্ডন"),
]

AIRLINES = [
    ("BG", "Biman Bangladesh Airlines", "বিমান বাংলাদেশ এয়ারলাইন্স"),
    ("BS", "US-Bangla Airlines", "ইউএস-বাংলা এয়ারলাইন্স"),
    ("EK", "Emirates", "এমিরেটস"),
    ("QR", "Qatar Airways", "কাতার এয়ারওয়েজ"),
    ("SV", "Saudia", "সৌদিয়া"),
    ("G9", "Air Arabia", "এয়ার অ্যারাবিয়া"),
]

DURATIONS_MINUTES = {
    "SHJ": 300,
    "LHR": 700,
    "DXB": 295,
    "JED": 375,
    "KUL": 235,
    "DOH": 325,
}

FLIGHTS = [
    {
        "number": "G9518",
        "airline": "G9",
        "destination": "SHJ",
        "offset": -180,  # departed ~3h ago
        "status": Flight.STATUS_DEPARTED,
        "block": "C",
        "counters": "33-36",
        "gate": "6",
        "terminal": "Terminal 2",
    },
    {
        "number": "BG001",
        "airline": "BG",
        "destination": "LHR",
        "offset": -40,  # gate closed ~40min ago
        "status": Flight.STATUS_GATE_CLOSED,
        "block": "A",
        "counters": "9-12",
        "gate": "3",
        "terminal": "Terminal 2",
    },
    {
        "number": "EK585",
        "airline": "EK",
        "destination": "DXB",
        "offset": 30,  # boarding now
        "status": Flight.STATUS_BOARDING,
        "block": "A",
        "counters": "11-14",
        "gate": "8",
        "terminal": "Terminal 2",
    },
    {
        "number": "SV804",
        "airline": "SV",
        "destination": "JED",
        "offset": 15,  # final call
        "status": Flight.STATUS_FINAL_CALL,
        "block": "B",
        "counters": "19-22",
        "gate": "4",
        "terminal": "Terminal 2",
    },
    {
        "number": "BS341",
        "airline": "BS",
        "destination": "KUL",
        "offset": 120,  # check-in open
        "status": Flight.STATUS_CHECK_IN_OPEN,
        "checkin_open": True,
        "block": "C",
        "counters": "5-8",
        "terminal": "Terminal 2",
    },
    {
        "number": "QR641",
        "airline": "QR",
        "destination": "DOH",
        "offset": 240,  # scheduled
        "status": Flight.STATUS_SCHEDULED,
        "block": "B",
        "counters": "27-29",
        "terminal": "Terminal 2",
    },
    {
        "number": "BG147",
        "airline": "BG",
        "destination": "DXB",
        "offset": 300,  # scheduled
        "status": Flight.STATUS_SCHEDULED,
        "block": "A",
        "counters": "17-20",
        "terminal": "Terminal 2",
    },
    {
        "number": "BG035",
        "airline": "BG",
        "destination": "JED",
        "offset": 60,  # delayed +1h -> est +2.5h
        "est_offset": 150,
        "status": Flight.STATUS_DELAYED,
        "block": "B",
        "counters": "23-26",
        "terminal": "Terminal 2",
    },
]


class Command(BaseCommand):
    help = "Reset and seed the mock AODB with today's demo flights (DAC departures)."

    @transaction.atomic
    def handle(self, *args, **options):
        TicketHandoff.objects.all().delete()
        TicketScan.objects.all().delete()
        JourneySession.objects.all().delete()
        Flight.objects.all().delete()
        Airline.objects.all().delete()
        Airport.objects.all().delete()

        airports = {code: Airport.objects.create(code=code, city=city, name=name, bangla_city=bn) for code, city, name, bn in AIRPORTS}
        airlines = {code: Airline.objects.create(code=code, name=name, bangla_name=bn) for code, name, bn in AIRLINES}
