from dataclasses import dataclass


@dataclass(frozen=True)
class POIFixture:
    poi_id: str
    name: str
    primary_category: str
    secondary_categories: list[str]
    coordinates: list[float]
    short_description: str
    city: str
    distance_from_route_m: int
    estimated_detour_m: int
    estimated_extra_minutes: int
    base_score: float
    walk_affinity: float
    drive_affinity: float
    badges: list[str]
    why_it_matters: list[str]
    provenance: dict[str, str]


FIXTURE_POIS: list[POIFixture] = [
    POIFixture(
        poi_id="poi-acequia-madre",
        name="Acequia Madre",
        primary_category="history",
        secondary_categories=["civic"],
        coordinates=[-105.9319, 35.6828],
        short_description=(
            "Historic irrigation corridor that still reads the city's water geography."
        ),
        city="santa-fe",
        distance_from_route_m=110,
        estimated_detour_m=380,
        estimated_extra_minutes=3,
        base_score=76.0,
        walk_affinity=0.9,
        drive_affinity=0.8,
        badges=["near this route", "within budget"],
        why_it_matters=[
            "high historical significance",
            "strong local landscape identity",
            "very low detour burden",
        ],
        provenance={"osm_id": "way/acequia-madre", "wikidata_id": "Q999001"},
    ),
    POIFixture(
        poi_id="poi-santa-fe-plaza",
        name="Santa Fe Plaza",
        primary_category="culture",
        secondary_categories=["history", "civic"],
        coordinates=[-105.9378, 35.6870],
        short_description=(
            "Historic civic core where colonial planning, commerce, "
            "and public life still intersect."
        ),
        city="santa-fe",
        distance_from_route_m=160,
        estimated_detour_m=520,
        estimated_extra_minutes=4,
        base_score=79.0,
        walk_affinity=1.0,
        drive_affinity=0.7,
        badges=["worth the detour", "local anchor"],
        why_it_matters=[
            "strong civic and historical legibility",
            "high interpretive value for settlement and public life",
            "reviewed landmark candidate",
        ],
        provenance={"osm_id": "way/santa-fe-plaza", "wikidata_id": "Q999002"},
    ),
    POIFixture(
        poi_id="poi-canyon-road-corridor",
        name="Canyon Road Arts Corridor",
        primary_category="art",
        secondary_categories=["culture"],
        coordinates=[-105.9170, 35.6844],
        short_description=(
            "Dense art corridor where street sequence and galleries read as a cultural landscape."
        ),
        city="santa-fe",
        distance_from_route_m=190,
        estimated_detour_m=650,
        estimated_extra_minutes=5,
        base_score=72.0,
        walk_affinity=0.95,
        drive_affinity=0.65,
        badges=["route-adjacent", "street-level legibility"],
        why_it_matters=[
            "high art and culture concentration",
            "strong walking relevance",
            "distinctive corridor character",
        ],
        provenance={"osm_id": "way/canyon-road", "wikipedia_title": "Canyon_Road"},
    ),
    POIFixture(
        poi_id="poi-rail-yard",
        name="Santa Fe Rail Yard District",
        primary_category="civic",
        secondary_categories=["history", "culture"],
        coordinates=[-105.9495, 35.6821],
        short_description=(
            "Former rail infrastructure turned civic corridor with strong labor "
            "and settlement traces."
        ),
        city="santa-fe",
        distance_from_route_m=210,
        estimated_detour_m=720,
        estimated_extra_minutes=5,
        base_score=74.0,
        walk_affinity=0.85,
        drive_affinity=0.8,
        badges=["worth the detour", "infrastructure trace"],
        why_it_matters=[
            "reveals labor and transportation history",
            "strong adaptive-reuse signal",
            "solid route fit",
        ],
        provenance={"osm_id": "way/rail-yard", "wikidata_id": "Q999004"},
    ),
    POIFixture(
        poi_id="poi-cross-of-the-martyrs",
        name="Cross of the Martyrs Overlook",
        primary_category="scenic",
        secondary_categories=["history"],
        coordinates=[-105.9348, 35.6917],
        short_description=(
            "Overlook with a strong topographic read on the city and visible historical framing."
        ),
        city="santa-fe",
        distance_from_route_m=300,
        estimated_detour_m=980,
        estimated_extra_minutes=7,
        base_score=68.0,
        walk_affinity=0.55,
        drive_affinity=0.88,
        badges=["worth the detour", "elevated view"],
        why_it_matters=[
            "high scenic payoff",
            "strong driving relevance",
            "connects terrain with historical framing",
        ],
        provenance={"osm_id": "node/cross-martyrs", "wikipedia_title": "Cross_of_the_Martyrs"},
    ),
]
