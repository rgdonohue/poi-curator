from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

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
    poi = cast(
        Any,
        SimpleNamespace(
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

    apply_wikidata_entity(poi, entity)

    assert poi.wikidata_id == "Q123"
    assert poi.wikipedia_title == "Santa_Fe_Plaza"
    assert poi.short_description == "historic plaza in Santa Fe, New Mexico"
    assert poi.signals.has_wikidata is True
    assert poi.signals.has_wikipedia is True
    assert poi.signals.entity_type_confidence >= 0.9
