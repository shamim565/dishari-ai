from apps.flights.models import Flight
from apps.journeys.models import JourneySession

JOURNEY_KEY = "journey_token"


def create_journey(*, flight, passenger_name, source, lang="en", seat="", pnr="", cabin="", extraction=None):
    return JourneySession.objects.create(
        passenger_name=passenger_name,
        flight=flight,
        seat=seat or "",
        pnr=pnr or "",
        cabin=cabin or "",
        lang=lang,
        source=source,
        extraction=extraction or {},
    )


def attach_journey(request, journey):
    request.session[JOURNEY_KEY] = journey.token


def get_active_journey(request):
    token = request.session.get(JOURNEY_KEY)
    if not token:
        return None
    journey = (
        JourneySession.objects.select_related(
            "flight", "flight__airline", "flight__origin", "flight__destination"
        )
        .filter(token=token)
        .first()
    )
    if not journey or not journey.is_active:
        request.session.pop(JOURNEY_KEY, None)
        return None
    return journey
