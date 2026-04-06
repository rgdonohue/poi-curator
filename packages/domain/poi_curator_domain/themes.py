from dataclasses import dataclass
from typing import Literal


ThemeSlug = Literal["water", "rail", "public_memory"]
ThemeStatus = Literal["candidate", "accepted", "suppressed"]
ThemeAssignmentBasis = Literal["rule", "evidence", "editorial", "mixed"]
ThemeEditorialDecision = Literal["force_include", "force_exclude", "needs_review"]


@dataclass(frozen=True)
class ThemeDefinitionSpec:
    theme_slug: ThemeSlug
    label: str
    description: str
    region_scope: str
    is_query_active: bool


THEME_DEFINITION_SPECS: tuple[ThemeDefinitionSpec, ...] = (
    ThemeDefinitionSpec(
        theme_slug="water",
        label="Water",
        description=(
            "Places that reveal acequia infrastructure, canal traces, water corridors, "
            "and the civic landscape shaped by water."
        ),
        region_scope="santa-fe",
        is_query_active=True,
    ),
    ThemeDefinitionSpec(
        theme_slug="rail",
        label="Rail",
        description=(
            "Places that reveal rail infrastructure, labor, circulation, and adaptive reuse."
        ),
        region_scope="santa-fe",
        is_query_active=False,
    ),
    ThemeDefinitionSpec(
        theme_slug="public_memory",
        label="Public Memory",
        description=(
            "Places where public commemoration, civic-historic framing, and staged memory "
            "are legible in the landscape."
        ),
        region_scope="santa-fe",
        is_query_active=False,
    ),
)


THEME_LABELS: dict[ThemeSlug, str] = {
    spec.theme_slug: spec.label for spec in THEME_DEFINITION_SPECS
}
QUERY_ACTIVE_THEME_SLUGS: frozenset[ThemeSlug] = frozenset(
    spec.theme_slug for spec in THEME_DEFINITION_SPECS if spec.is_query_active
)


def is_query_theme_active(theme_slug: ThemeSlug) -> bool:
    return theme_slug in QUERY_ACTIVE_THEME_SLUGS
