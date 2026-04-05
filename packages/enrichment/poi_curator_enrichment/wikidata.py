from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import orjson
from poi_curator_domain.settings import get_settings


@dataclass(frozen=True)
class WikidataEntity:
    entity_id: str
    label: str | None
    description: str | None
    wikipedia_title: str | None


def fetch_wikidata_entity(entity_id: str) -> WikidataEntity:
    return fetch_wikidata_entities([entity_id])[entity_id]


def fetch_wikidata_entities(entity_ids: list[str]) -> dict[str, WikidataEntity]:
    if not entity_ids:
        return {}

    settings = get_settings()
    query = urlencode(
        {
            "action": "wbgetentities",
            "format": "json",
            "ids": "|".join(entity_ids),
            "props": "labels|descriptions|sitelinks",
            "languages": "en",
            "sitefilter": "enwiki",
        }
    )
    request = Request(
        f"{settings.wikidata_api_url}?{query}",
        headers={"User-Agent": "poi-curator/0.1.0", "Accept": "application/json"},
    )
    with urlopen(request, timeout=settings.wikidata_timeout_seconds) as response:
        payload = orjson.loads(response.read())
    return {
        current_entity_id: parse_wikidata_entity_payload(payload, current_entity_id)
        for current_entity_id in entity_ids
    }


def parse_wikidata_entity_payload(
    payload: dict[str, Any],
    entity_id: str,
) -> WikidataEntity:
    entity = payload.get("entities", {}).get(entity_id, {})
    labels = entity.get("labels", {})
    descriptions = entity.get("descriptions", {})
    sitelinks = entity.get("sitelinks", {})
    return WikidataEntity(
        entity_id=entity_id,
        label=_language_value(labels, "en"),
        description=_language_value(descriptions, "en"),
        wikipedia_title=sitelinks.get("enwiki", {}).get("title"),
    )


def extract_wikidata_id(tags: dict[str, Any]) -> str | None:
    value = tags.get("wikidata")
    if value is None:
        return None
    entity_id = str(value).strip()
    if not entity_id.startswith("Q"):
        return None
    return entity_id


def extract_wikipedia_title(tags: dict[str, Any]) -> str | None:
    value = tags.get("wikipedia")
    if value is None:
        return None
    text = str(value).strip()
    if ":" in text:
        _, title = text.split(":", maxsplit=1)
        return title.replace(" ", "_")
    return text.replace(" ", "_")


def _language_value(values: dict[str, Any], lang: str) -> str | None:
    preferred = values.get(lang)
    if isinstance(preferred, dict):
        value = preferred.get("value")
        if value:
            return str(value)

    for candidate in values.values():
        if isinstance(candidate, dict):
            value = candidate.get("value")
            if value:
                return str(value)
    return None
