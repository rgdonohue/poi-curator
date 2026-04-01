from dataclasses import dataclass


@dataclass(frozen=True)
class RegionSpec:
    slug: str
    name: str
    bbox: tuple[float, float, float, float]
    city: str
    region: str
    country: str


SUPPORTED_REGIONS: dict[str, RegionSpec] = {
    "santa-fe": RegionSpec(
        slug="santa-fe",
        name="Santa Fe",
        bbox=(35.612, -106.083, 35.744, -105.854),
        city="santa-fe",
        region="new-mexico",
        country="usa",
    ),
}


def get_region(region_slug: str) -> RegionSpec:
    try:
        return SUPPORTED_REGIONS[region_slug]
    except KeyError as exc:
        raise ValueError(f"Unsupported region: {region_slug}") from exc
