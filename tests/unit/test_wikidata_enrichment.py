from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from poi_curator_domain.db import POIEvidence, SourceRegistry
from poi_curator_enrichment.pipeline import (
    apply_wikidata_entity,
    should_replace_short_description,
)
from poi_curator_enrichment.wikidata import (
    WikidataEntity,
    extract_wikidata_id,
    extract_wikipedia_title,
    parse_wikidata_entity_payload,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def get(self, model: type[Any], key: str) -> Any:
        return None

    def scalar(self, statement: Any) -> Any:
        return None

    def add(self, item: Any) -> None:
        self.added.append(item)


def test_parse_wikidata_entity_payload_extracts_label_description_and_enwiki() -> None:
    payload = {
        "entities": {
            "Q123": {
                "labels": {"en": {"value": "Santa Fe Plaza"}},
                "descriptions": {"en": {"value": "historic plaza in Santa Fe, New Mexico"}},
                "sitelinks": {"enwiki": {"title": "Santa_Fe_Plaza"}},
            }
        }
    }

    entity = parse_wikidata_entity_payload(payload, "Q123")

    assert entity.entity_id == "Q123"
    assert entity.label == "Santa Fe Plaza"
    assert entity.description == "historic plaza in Santa Fe, New Mexico"
    assert entity.wikipedia_title == "Santa_Fe_Plaza"


def test_extract_wikidata_and_wikipedia_titles_from_osm_tags() -> None:
    tags = {
        "wikidata": "Q123",
        "wikipedia": "en:Santa_Fe_Plaza",
    }

    assert extract_wikidata_id(tags) == "Q123"
    assert extract_wikipedia_title(tags) == "Santa_Fe_Plaza"


def test_should_replace_machine_generated_description() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            short_description="Civic space that helps explain the structure of public life.",
            normalized_subcategory="civic_space_plaza",
        ),
    )

    assert should_replace_short_description(
        poi,
        "historic plaza in Santa Fe, New Mexico",
    ) is True


def test_apply_wikidata_entity_updates_identity_and_description() -> None:
    session = FakeSession()
    poi = cast(
        Any,
        SimpleNamespace(
            poi_id="poi-123",
            wikidata_id=None,
            wikipedia_title=None,
            short_description="Civic space that helps explain the structure of public life.",
            normalized_subcategory="civic_space_plaza",
            updated_at=datetime.now(UTC),
            signals=SimpleNamespace(
                has_wikidata=False,
                has_wikipedia=False,
                entity_type_confidence=0.4,
                description_quality=1.0,
                computed_at=datetime.now(UTC),
            ),
        ),
    )
    entity = WikidataEntity(
        entity_id="Q123",
        label="Santa Fe Plaza",
        description="historic plaza in Santa Fe, New Mexico",
        wikipedia_title="Santa_Fe_Plaza",
    )

    apply_wikidata_entity(cast(Any, session), poi, entity)

    assert poi.wikidata_id == "Q123"
    assert poi.wikipedia_title == "Santa_Fe_Plaza"
    assert poi.short_description == "historic plaza in Santa Fe, New Mexico"
    assert poi.signals.has_wikidata is True
    assert poi.signals.has_wikipedia is True
    assert poi.signals.entity_type_confidence >= 0.9


def test_apply_wikidata_entity_creates_evidence_before_canonical_write() -> None:
    session = FakeSession()
    poi = cast(
        Any,
        SimpleNamespace(
            poi_id="poi-456",
            wikidata_id=None,
            wikipedia_title=None,
            short_description=None,
            normalized_subcategory="historic_site",
            updated_at=datetime.now(UTC),
            signals=None,
        ),
    )
    entity = WikidataEntity(
        entity_id="Q456",
        label="Historic Site",
        description="historic place in New Mexico",
        wikipedia_title="Historic_Site",
    )

    apply_wikidata_entity(cast(Any, session), poi, entity, wikipedia_title_hint="OSM_Title")

    source = next(item for item in session.added if isinstance(item, SourceRegistry))
    evidence = next(item for item in session.added if isinstance(item, POIEvidence))
    assert source.source_id == "wikidata"
    assert evidence.poi_id == "poi-456"
    assert evidence.source_id == "wikidata"
    assert evidence.external_record_id == "Q456"
    assert evidence.raw_evidence_json == {
        "entity_id": "Q456",
        "label": "Historic Site",
        "description": "historic place in New Mexico",
        "wikipedia_title": "Historic_Site",
        "wikipedia_title_hint": "OSM_Title",
    }
    assert poi.wikidata_id == "Q456"
