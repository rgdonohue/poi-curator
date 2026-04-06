from pathlib import Path
from typing import Any

import httpx
import orjson
from poi_curator_domain.regions import RegionSpec
from poi_curator_domain.settings import get_settings

OVERPASS_FILTERS: list[tuple[str, str | None]] = [
    ("historic", None),
    ("tourism", "museum|gallery|artwork|viewpoint"),
    ("amenity", "theatre|marketplace|place_of_worship"),
    ("place", "neighbourhood"),
    ("man_made", None),
    ("waterway", None),
    ("natural", None),
    ("leisure", "park"),
    ("highway", "pedestrian"),
]


def build_overpass_query(region: RegionSpec) -> str:
    south, west, north, east = region.bbox
    bbox = f"({south},{west},{north},{east})"
    clauses: list[str] = []
    for key, value_pattern in OVERPASS_FILTERS:
        for element_type in ("node", "way", "relation"):
            if value_pattern is None:
                clauses.append(f'{element_type}["{key}"]{bbox};')
            else:
                clauses.append(f'{element_type}["{key}"~"{value_pattern}"]{bbox};')
    joined_clauses = "\n  ".join(clauses)
    return (
        "[out:json][timeout:60];\n"
        "(\n"
        f"  {joined_clauses}\n"
        ");\n"
        "out body center geom tags;"
    )


def fetch_overpass_elements(region: RegionSpec) -> list[dict[str, Any]]:
    settings = get_settings()
    query = build_overpass_query(region)
    endpoints = [settings.overpass_url]
    if settings.overpass_fallback_url not in endpoints:
        endpoints.append(settings.overpass_fallback_url)

    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            with httpx.Client(timeout=settings.overpass_timeout_seconds) as client:
                response = client.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": "poi-curator/0.1.0"},
                )
                response.raise_for_status()
                payload = response.json()
            return list(payload.get("elements", []))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


def load_overpass_elements_from_file(path: Path) -> list[dict[str, Any]]:
    payload = orjson.loads(path.read_bytes())
    return list(payload.get("elements", []))
