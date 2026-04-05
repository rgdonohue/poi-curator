from poi_curator_domain.descriptions import (
    choose_short_description,
    is_low_quality_description,
)


def test_low_quality_description_flags_mapper_maintenance_notes() -> None:
    assert is_low_quality_description("survey new height, confirm former height") is True


def test_choose_short_description_falls_back_for_low_quality_source_text() -> None:
    description = choose_short_description(
        normalized_subcategory="monument_memorial",
        stored_description="survey new height, confirm former height",
    )

    assert description == "Monument or memorial with strong public memory value."
