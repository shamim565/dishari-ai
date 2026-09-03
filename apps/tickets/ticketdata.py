import random
from datetime import timedelta

PASSENGERS = [
    ("MR", "Md Rahim Uddin"),
    ("MR", "Abdul Karim Mia"),
    ("MRS", "Shahida Begum"),
    ("MR", "Jahangir Alam"),
    ("MS", "Nusrat Jahan"),
    ("MR", "Md Sohag Mia"),
    ("MRS", "Farida Yesmin"),
    ("MR", "Kamrul Hasan"),
]

SEATS = ["14A", "18C", "22F", "9B", "27D", "31A", "12E", "25C"]

AIRLINE_TICKET_PREFIX = {
    "BG": "997",
    "BS": "959",
    "EK": "176",
    "QR": "157",
    "SV": "065",
    "G9": "514",
}

BAGGAGE_ALLOWANCE = {
    "BG": "30 KG",
    "BS": "20 KG",
    "EK": "30 KG",
    "QR": "30 KG",
    "SV": "2 PC",
    "G9": "30 KG",
}

FARE_BY_DESTINATION = {
    "DXB": 42500,
    "SHJ": 41000,
    "JED": 49500,
    "KUL": 38500,
    "DOH": 47000,
    "LHR": 98500,
}

FARE_BASES = ["YLBR", "MLBR", "QLBR", "TLBR"]


def ticket_data(flight, index=0):
    rng = random.Random(f"ticket:{flight.number}:{flight.date}")
    title, name_display = PASSENGERS[index % len(PASSENGERS)]
    name_print = name_display.upper()
    pnr = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))

    prefix = AIRLINE_TICKET_PREFIX.get(flight.airline.code, "000")
    ticket_number = f"{prefix}-{''.join(str(rng.randint(0, 9)) for _ in range(10))}"

    base_fare = FARE_BY_DESTINATION.get(flight.destination.code, 40000)
    fare = base_fare + rng.randint(0, 15) * 100
    taxes = fare * 185 // 1000
    taxes = taxes // 10 * 10

    return {
        "title": title,
        "name_display": name_display,
        "name_print": name_print,
        "pnr": pnr,
        "seat": SEATS[index % len(SEATS)],
        "cabin": "ECONOMY",
        "passenger_type": "ADULT",
        "ticket_number": ticket_number,
        "baggage": BAGGAGE_ALLOWANCE.get(flight.airline.code, "30 KG"),
        "fare_basis": rng.choice(FARE_BASES),
        "fare": fare,
        "taxes": taxes,
        "total": fare + taxes,
        "issue_date": flight.date - timedelta(days=5),
        "agent": "DHAKA TRAVEL AGENCY (DEMO)",
        "form_of_payment": "CARD",
    }
