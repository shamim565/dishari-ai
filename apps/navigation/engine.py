import math
from collections import defaultdict, deque
from dataclasses import dataclass, field

from apps.navigation.models import Location, RouteSegment

WALK_METERS_PER_MINUTE = 70

LOCATION_INDEX = {}


@dataclass
class Step:
    instruction_en: str
    instruction_bn: str
    distance_m: int
    to_code: str
    to_name_en: str
    to_name_bn: str


@dataclass
class RouteResult:
    from_location: Location
    to_location: Location
    steps: list = field(default_factory=list)
    distance_m: int = 0

    @property
    def walk_minutes(self):
        return max(1, math.ceil(self.distance_m / WALK_METERS_PER_MINUTE))

    @property
    def points(self):
        coords = [(self.from_location.x, self.from_location.y)]
        for step in self.steps:
            loc = LOCATION_INDEX.get(step.to_code)
            if loc:
                coords.append((loc.x, loc.y))
        return " ".join(f"{x},{y}" for x, y in coords)


def refresh_location_index():
    LOCATION_INDEX.clear()
    for loc in Location.objects.all():
        LOCATION_INDEX[loc.code] = loc


def _adjacency():
    adjacency = defaultdict(list)
    for segment in RouteSegment.objects.select_related("from_location", "to_location"):
        adjacency[segment.from_location.code].append((segment.to_location.code, segment))
        adjacency[segment.to_location.code].append((segment.from_location.code, segment))
    return adjacency


def _build_steps(path, start_code):
    steps = []
    current = start_code
    for segment in path:
        if segment.from_location.code == current:
            destination = segment.to_location
        else:
            destination = segment.from_location
        steps.append(
            Step(
                instruction_en=segment.instruction_en,
                instruction_bn=segment.instruction_bn,
                distance_m=segment.distance_m,
                to_code=destination.code,
                to_name_en=destination.name_en,
                to_name_bn=destination.name_bn,
            )
        )
        current = destination.code
    return steps


def find_route(from_loc, to_loc):
    if from_loc is None or to_loc is None:
        return None
    refresh_location_index()
    if from_loc.code == to_loc.code:
        return RouteResult(from_location=from_loc, to_location=to_loc)

    adjacency = _adjacency()
    queue = deque([(from_loc.code, [])])
    visited = {from_loc.code}
    while queue:
        node, path = queue.popleft()
        for next_code, segment in adjacency[node]:
            if next_code in visited:
                continue
            new_path = path + [segment]
            if next_code == to_loc.code:
                return RouteResult(
                    from_location=from_loc,
                    to_location=to_loc,
                    steps=_build_steps(new_path, from_loc.code),
                    distance_m=sum(s.distance_m for s in new_path),
                )
            visited.add(next_code)
            queue.append((next_code, new_path))
    return None
