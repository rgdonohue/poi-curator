# HPD Address-Geocoding Pass

Date: 2026-05-11

Scope: 136 retained `source_id='nm_hpd'` no-coordinate diagnostics from the State Register
workbook. Coordinates were derived with Nominatim from workbook address fields and are explicitly
review aids, not source-published geometry. No geocoded record was promoted to a canonical POI.

## Workbook Address Fields

The retained diagnostics preserve the workbook row under `raw_payload_json.record`.

| Address field | Diagnostics with value |
|---|---:|
| `Address` | 88 |
| `T` legacy column mirror | 88 |

Forty-eight diagnostics had no usable street-address value and were not geocoded.

## Geocoding Outcomes

| Outcome | Count |
|---|---:|
| Successfully geocoded inside Santa Fe County | 64 |
| Failed: no usable address | 48 |
| Failed: no Nominatim result | 23 |
| Failed: result outside Santa Fe County | 1 |

Nominatim was queried with an identifying `poi-curator` User-Agent and one-request-per-second
spacing for uncached requests. Returned coordinates are tagged in diagnostic JSON with
`derived_coordinate=true`, `geocoder='Nominatim'`, the source address, query, display name, and OSM
license text.
Each diagnostic geocoding payload is explicitly tagged with `source_id='nm_hpd'` and
`evidence_type='geocoded_coordinate'`. Because no geocoded row matched an existing canonical, no
`poi_evidence` rows could be created in this pass; the candidate records remain diagnostic review
items until a curator approves an attachment or promotion target.

## Matcher Outcomes

| Matcher outcome | Count | Database action |
|---|---:|---|
| Matched existing canonical | 0 | No `geocoded_coordinate` evidence rows created. |
| Ambiguous | 0 | No ambiguous geocoded diagnostics created. |
| Candidate canonical review | 64 | Diagnostics moved to `status='geocoded_candidate_review'`; match logs written with `decision='candidate_review'`. |

The existing spatial+name matcher did not attach any geocoded HPD rows to current canonicals. This
is expected for many rows because HPD register labels often use formal property names while nearby
OSM records use campus, school, museum, or address labels.

## Candidate Examples

| Register ID | HPD name | Geocoded result |
|---|---|---|
| 1279 | Santa Fe County Courthouse | Santa Fe County John Gaw Meem Historic Building, 102 Grant Avenue |
| 141 | La Conquistadora Chapel | Cathedral Place, Barrio de Analco Historic District |
| 1470 | Connor Hall (NMSD) | New Mexico School for the Deaf, 1060 Cerrillos Road |
| 1904 | Carlos Gilbert Elementary School | Carlos Gilbert Elementary School, 300 Griffin Street |
| 1908 | La Armeria de Santa Fe/Santa Fe Armory | Santa Fe Children's Museum, 1050 Old Pecos Trail |
| 2074 | El Rancho de las Golondrinas | El Rancho de las Golondrinas, 334 Los Pinos Road |
| 2075 | Federal Building and Post Office | Joseph M. Montoya Federal Building, 120 South Federal Place |
| 2088 | New Mexico Territorial and State Capitol | Bataan Memorial Building, 407 Galisteo Street |
| 211 | Prince Plaza | Prince Plaza, 107-117 East Palace Avenue |
| 303 | Rush, Olive, Studio | 630 Canyon Road |

## Diagnostic Count Delta

| Diagnostic bucket | Before | After |
|---|---:|---:|
| HPD no-coordinate diagnostics, `status='unreviewed'` | 136 | 72 |
| HPD geocoded candidate review queue | 0 | 64 |

The 72 remaining unreviewed diagnostics are still no-coordinate retained records: 48 have no usable
address, 23 did not resolve through Nominatim, and one resolved outside Santa Fe County. The 64
geocoded rows are better editorial leads, but still require human review before canonical
promotion because their coordinates are address-derived rather than source-published geometry.
