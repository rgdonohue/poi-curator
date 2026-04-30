from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from poi_curator_domain.schemas import EncounterAnchor, ExtendedPlaceContext, PlaceForm
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

_CORRIDOR_DISPLAY_HINT = (
    "Extended corridor; prefer encounter anchors over the centroid for map placement."
)
_AREA_DISPLAY_HINT = (
    "Extended area; prefer encounter or interior anchors over a single fixed dot."
)
_CORRIDOR_SAMPLE_POSITIONS = (0.2, 0.5, 0.8)


@dataclass(frozen=True)
class PlaceRepresentation:
    anchor_point: Point
    extended_place: ExtendedPlaceContext | None = None


def build_place_representation(
    poi: Any,
    geometry: BaseGeometry,
    *,
    query_geometry: BaseGeometry | None = None,
    fallback_point: Point | None = None,
) -> PlaceRepresentation:
    anchor_fallback = fallback_point or _representative_point(geometry)
    place_form = infer_place_form(poi, geometry)
    if place_form is None:
        return PlaceRepresentation(anchor_point=anchor_fallback)

    primary_anchor = _primary_anchor(
        geometry,
        query_geometry=query_geometry,
        fallback_point=anchor_fallback,
    )
    return PlaceRepresentation(
        anchor_point=primary_anchor,
        extended_place=ExtendedPlaceContext(
            place_form=place_form,
            encounter_mode="along_corridor" if place_form == "corridor" else "within_area",
            display_hint=(
                _CORRIDOR_DISPLAY_HINT if place_form == "corridor" else _AREA_DISPLAY_HINT
            ),
            encounter_anchors=_build_encounter_anchors(
                geometry,
                place_form=place_form,
                primary_anchor=primary_anchor,
            ),
        ),
    )


def infer_place_form(poi: Any, geometry: BaseGeometry) -> PlaceForm | None:
    raw_tags = dict(getattr(poi, "raw_tag_summary_json", {}) or {})
    normalized_subcategory = str(getattr(poi, "normalized_subcategory", "") or "")
    canonical_name = str(getattr(poi, "canonical_name", "") or "").casefold()
    geometry_type = geometry.geom_type
    if geometry_type in {"LineString", "MultiLineString"}:
        return "corridor"
    if geometry_type in {"Polygon", "MultiPolygon"} and _supports_area_form(
        normalized_subcategory=normalized_subcategory,
        raw_tags=raw_tags,
        canonical_name=canonical_name,
    ):
        return "area"

    if normalized_subcategory == "neighborhood_corridor":
        return "corridor"
    if _supports_area_form(
        normalized_subcategory=normalized_subcategory,
        raw_tags=raw_tags,
        canonical_name=canonical_name,
    ):
        return "area"
    if raw_tags.get("man_made") == "canal":
        return "corridor"
    return None


def _supports_area_form(
    *,
    normalized_subcategory: str,
    raw_tags: dict[str, Any],
    canonical_name: str,
) -> bool:
    if normalized_subcategory in {"historic_district", "civic_space_plaza"}:
        return True
    if raw_tags.get("historic") == "district":
        return True
    if raw_tags.get("place") in {"neighbourhood", "quarter", "suburb"}:
        return True
    return any(token in canonical_name for token in ("district", "plaza", "compound"))


def _primary_anchor(
    geometry: BaseGeometry,
    *,
    query_geometry: BaseGeometry | None,
    fallback_point: Point,
) -> Point:
    if query_geometry is not None and not query_geometry.is_empty:
        _, geometry_point = nearest_points(query_geometry, geometry)
        if isinstance(geometry_point, Point) and not geometry_point.is_empty:
            return geometry_point
    return fallback_point


def _build_encounter_anchors(
    geometry: BaseGeometry,
    *,
    place_form: PlaceForm,
    primary_anchor: Point,
) -> list[EncounterAnchor]:
    anchors: list[EncounterAnchor] = [
        EncounterAnchor(
            label="primary encounter",
            coordinates=[primary_anchor.x, primary_anchor.y],
            kind="encounter",
            is_primary=True,
        )
    ]

    if place_form == "corridor":
        if geometry.geom_type not in {"LineString", "MultiLineString"}:
            return anchors
        line = _longest_line(geometry)
        for index, point in enumerate(
            _dedupe_points(
                [
                    line.interpolate(position, normalized=True)
                    for position in _CORRIDOR_SAMPLE_POSITIONS
                ],
                primary_anchor,
            ),
            start=1,
        ):
            anchors.append(
                EncounterAnchor(
                    label=f"corridor segment {index}",
                    coordinates=[point.x, point.y],
                    kind="segment",
                )
            )
        return anchors

    center_point = _representative_point(geometry)
    for point in _dedupe_points([center_point], primary_anchor):
        anchors.append(
            EncounterAnchor(
                label="area center",
                coordinates=[point.x, point.y],
                kind="center",
            )
        )
    return anchors


def _dedupe_points(points: list[Point], *existing: Point) -> list[Point]:
    deduped: list[Point] = []
    seen = {
        _point_key(point)
        for point in existing
        if isinstance(point, Point) and not point.is_empty
    }
    for point in points:
        if point.is_empty:
            continue
        point_key = _point_key(point)
        if point_key in seen:
            continue
        seen.add(point_key)
        deduped.append(point)
    return deduped


def _point_key(point: Point) -> tuple[float, float]:
    return (round(point.x, 6), round(point.y, 6))


def _longest_line(geometry: BaseGeometry) -> LineString:
    if isinstance(geometry, LineString):
        return geometry
    if isinstance(geometry, MultiLineString):
        return max(geometry.geoms, key=lambda item: item.length)
    if isinstance(geometry, Point):
        return LineString([(geometry.x, geometry.y), (geometry.x, geometry.y)])
    centroid = geometry.centroid
    return LineString([(centroid.x, centroid.y), (centroid.x, centroid.y)])


def _representative_point(geometry: BaseGeometry) -> Point:
    if isinstance(geometry, Point):
        return geometry
    if isinstance(geometry, (LineString, MultiLineString)):
        line = _longest_line(geometry)
        return line.interpolate(0.5, normalized=True) if line.length else Point(line.coords[0])
    if isinstance(geometry, Polygon):
        return geometry.representative_point()
    representative_point = geometry.representative_point()
    if isinstance(representative_point, Point) and not representative_point.is_empty:
        return representative_point
    centroid = geometry.centroid
    if isinstance(centroid, Point) and not centroid.is_empty:
        return centroid
    return Point()
