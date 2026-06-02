"""Same-feature canonicalization for the Detour merged POI export.

Pure functions only: no DB access, no file I/O. Collapses OSM
relation+member-way+node duplicates into a single canonical row while
preserving legitimately co-located distinct features.
"""

from __future__ import annotations

import math

from poi_curator_ingestion.matching import normalize_name_tokens

# Structural / type tokens that must never be the *only* shared token between
# two rows. Layered on top of matching.COMMON_AFFIXES (the, de, san, fe, ...)
# and the directional words below, which normalize_name_tokens does NOT strip.
STRUCTURAL_TOKENS: frozenset[str] = frozenset(
    {
        "house",
        "park",
        "building",
        "gallery",
        "studio",
        "annex",
        "site",
        "center",
        "centre",
        "complex",
        "compound",
        # Plural residues from normalize_name_tokens (strips trailing "s",
        # does not handle y->ies): gallery/annex/complex.
        "gallerie",
        "annexe",
        "complexe",
    }
)
DIRECTIONAL_TOKENS: frozenset[str] = frozenset(
    {"east", "west", "north", "south", "northeast", "northwest", "southeast", "southwest"}
)
_NON_SIGNIFICANT = STRUCTURAL_TOKENS | DIRECTIONAL_TOKENS

_EARTH_RADIUS_M = 6_371_000.0


def significant_tokens(name: str) -> set[str]:
    """Identity-bearing tokens: normalized tokens minus structural/directional ones."""
    return {token for token in normalize_name_tokens(name) if token not in _NON_SIGNIFICANT}


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two [lon, lat] points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))
