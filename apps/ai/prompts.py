TICKET_FIELDS = [
    "passenger_name",
    "airline_name",
    "airline_code",
    "flight_number",
    "origin_code",
    "destination_code",
    "date",
    "departure_time",
    "pnr",
    "seat",
    "cabin",
    "boarding_group",
    "confidence",
]

TICKET_SYSTEM_PROMPT = (
    "You are a precise airport travel-document OCR engine. "
    "You read airline e-tickets, itineraries and boarding passes and extract structured data. "
    "You never invent values that are not visible in the image. "
    "Respond with a single JSON object only - no markdown, no commentary."
)

TICKET_INSTRUCTION = (
    "Extract the flight details from this travel document image. "
    "Return JSON with exactly these keys: "
    + ", ".join(TICKET_FIELDS)
    + ". "
    "Rules: origin_code and destination_code are 3-letter IATA airport codes; "
    "airline_code is the 2-character airline code (e.g. BG); "
    "flight_number is the marketing flight number including the airline code (e.g. BG147); "
    "date must be YYYY-MM-DD; departure_time must be 24-hour HH:MM; "
    "confidence is a number between 0 and 1 describing overall extraction confidence. "
    "Use null for any field that is not readable or not present."
)
