# GNIS Quality Spot-Check

Generated: 2026-05-02

Scope: read-only editorial spot-check of 15 randomly sampled active `primary_source = 'gnis'` canonicals from the live local database. The admin viewer was opened, Coverage was checked for GNIS source counts, and the POI List source filter was set to `gnis` for review context. The sample below was drawn with `ORDER BY random()` from the 117 GNIS-primary canonicals.

## Summary

| Editorial bucket | Count | Notes |
|---|---:|---|
| Clearly valuable or promising with editorial framing | 10 | Mostly acequia/canal traces, named communities, and land-grant/civil geography that fill real OSM gaps but often need context before Detour surfacing. |
| Technically named but low immediate Detour value | 4 | Broad administrative/civil labels or generic populated-place points with weak stop-shaped value. |
| Likely duplicate or conflation miss | 1 | One sampled record belongs to an Eldorado/El Dorado GNIS cluster that should be reviewed as a possible duplicate/variant set. |

## Sample Notes

| Sample | Feature class | Coordinates | Nearest non-GNIS within 150 m | Editorial bucket | Note |
|---|---|---|---|---|---|
| Acequia de la Otra Banda | Canal | 35.892248, -106.063357 | None | Clearly valuable | Named acequia/canal trace; strong water-system value if interpreted carefully. |
| Cieneguilla | Populated Place | 35.595588, -106.123634 | None | Clearly valuable | Historic community/geography; useful gap filler, though not necessarily a single stop. |
| Eldorado at Santa Fe | Populated Place | 35.526424, -105.934742 | None | Likely duplicate | Part of a GNIS cluster with `El Dorado` / `El Dorado at Santa Fe`; review as duplicate or variant geography. |
| El Rancho | Populated Place | 35.889192, -106.079746 | None | Clearly valuable | Named community with likely acequia/settlement context; useful source-backed geographic anchor. |
| En Medio | Populated Place | 35.825861, -105.904465 | None | Clearly valuable | Named place connected to Rio en Medio geography; promising editorial context. |
| Jacona Grant | Civil | 35.841415, -106.039190 | None | Clearly valuable | Land-grant/civil geography has interpretive value, but representative-point display needs review. |
| Jaconita | Populated Place | 35.886137, -106.060023 | Lujan--Ortiz House, 89.9 m | Clearly valuable | Nearby NRHP house is a different kind of feature; not an obvious duplicate. |
| La Cienega | Populated Place | 35.562811, -106.130856 | None | Clearly valuable | Strong cultural-landscape candidate; likely useful for water/settlement context. |
| La Loma | Populated Place | 35.619477, -105.930576 | None | Low immediate value | Named point with thin context in current corpus; keep as candidate, not prominent stop. |
| Mesita de Juana Lopez Grant | Civil | 35.449204, -106.190301 | None | Clearly valuable | Land-grant geography is valuable for time-depth, but broad and needs editorial framing. |
| Potrero | Populated Place | 35.989747, -105.933632 | None | Low immediate value | Technically named, but current record alone gives limited Detour value. |
| Potrero Ditch | Canal | 35.991969, -105.936410 | None | Clearly valuable | Named ditch/acequia trace; good water-system evidence candidate. |
| Salvador Gonzales | Civil | 35.688920, -105.911132 | None | Low immediate value | Civil label is source-backed but not stop-shaped; needs stronger context before surfacing. |
| Santa Fe Division | Civil | 35.675069, -105.946558 | None | Low immediate value | Administrative geography; useful provenance, weak as canonical POI. |
| Santo Nino | Populated Place | 35.997801, -106.062801 | None | Clearly valuable | Named community likely worth retaining as a curation lead, with local-context review needed. |

## Recommendation

The current GNIS feature-class filter is too permissive for automatic canonical creation, but useful for candidate discovery and provenance. `Canal` records are the strongest fit for Detour's water/cultural-landscape layer. `Civil` and `Populated Place` records should probably remain ingested as evidence or review candidates unless they have corroborating local/heritage context, because several are broad administrative geographies or settlement labels rather than route-plausible stops. No matcher tuning should happen in this pass; the next scoped task should decide whether GNIS civil/populated-place records need a review-first path instead of immediate canonical creation.
