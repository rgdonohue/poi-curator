# NRHP Retained Diagnostics Triage

Date: 2026-05-01

Scope: the 19 legacy `nrhp_listed_properties` diagnostics that remained after the coordinate-bearing NRHP spatial run.

## Summary

| Category | Count | Database status |
|---|---:|---|
| Addressable now via City GIS or manual coordinate entry | 11 | `queued_next_ingest` |
| Genuinely off-grid or restricted for now | 7 | `out_of_scope` |
| Worth manual coordinate entry by a curator | 1 | `manual_review` |

## Detail

| NRHP ID | Name | Address | Category | Triage | Next action |
|---|---|---|---|---|---|
| 07000950 | Arroyo Hondo Pueblo | Address Restricted | SITE | out_of_scope_now | Address restricted archaeological pueblo record; do not add public coordinates in the next automated pass. |
| 100000828 | Meem, John Gaw and Faith Bemis, House | 3707 Old Santa Fe Trail | building | addressable_next_ingest | Street address present; queue geocode/manual coordinate check for the Meem house. |
| 100003031 | Pond-Kelly House | 535 E Palace Ave. | building | addressable_next_ingest | Street address present on Palace Avenue; queue geocode/manual coordinate check. |
| 100004030 | John Gaw Meem Architects Office | 1101 Camino De Cruz Blanca | building | addressable_next_ingest | Street address present on Camino de Cruz Blanca; queue geocode/manual coordinate check. |
| 100004033 | Agua Fria Schoolhouse Site | Address Restricted | site | out_of_scope_now | Address restricted schoolhouse site; keep out of scope until a curator approves a public point. |
| 100004822 | Nordfeldt, B. J. O. and Margaret Doolittle, House | 460 Camino de las Animas | building | addressable_next_ingest | Street address present on Camino de las Animas; queue geocode/manual coordinate check. |
| 100006766 | Hyde Memorial State Park | 740 Hyde Park Rd. (NM 475) | district | addressable_next_ingest | Park road address present; likely addressable via park/city/county GIS or manual coordinate entry. |
| 100008430 | El Rancho de las Golondrinas | 334 Los Pinos Rd. | district | addressable_next_ingest | Public site address present for El Rancho de las Golondrinas; queue coordinate entry. |
| 100008474 | U.S. Post Office and Federal Building | 120 South Federal Pl. | building | addressable_next_ingest | Federal Place address present; queue coordinate entry. |
| 100009668 | Immaculate Heart of Mary Seminary | 49 & 50 Mt. Carmel Road | district | addressable_next_ingest | Mount Carmel Road address present; queue coordinate entry. |
| 100011470 | New Mexico Territorial and State Capitol | 407 Galisteo Street | building | addressable_next_ingest | Galisteo Street address present; queue coordinate entry and compare to capitol complex POI. |
| 11000168 | Camino Real-La Bajada Mesa Section | Address Restricted | SITE | out_of_scope_now | Address restricted Camino Real segment; no public geometry in current feed. |
| 11000170 | Camino Real-Canon de las Bocas Section | Address Restricted | SITE | out_of_scope_now | Address restricted Camino Real segment; no public geometry in current feed. |
| 11000530 | La Armeria de Santa Fe | 1050 Old Pecos Tr. | BUILDING | addressable_next_ingest | Old Pecos Trail address present; queue coordinate entry. |
| 13000774 | El Rancho de las Golondrinas Section-El Camino Real de Tierra Adento | Address Restricted | SITE | out_of_scope_now | Address restricted Camino Real section; no public geometry in current feed. |
| 15000495 | St. John's College-Santa Fe, New Mexico | 1160 Camino Cruz Blanca | DISTRICT | manual_curator_coordinate | District-scale campus listing. Needs curator-selected representative point or polygon source, not simple address geocoding. |
| 16000588 | Santa Fe National Cemetery | 501 N. Guadalupe St. | district | addressable_next_ingest | National Cemetery address present; queue coordinate entry. |
| 66000490 | San Lazaro | Address Restricted | SITE | out_of_scope_now | Address restricted archaeological site; no public coordinate entry without deliberate curator approval. |
| 75001171 | Shonnard, Eugenie, House | Address Restricted | BUILDING | out_of_scope_now | Address restricted private/residential building record; keep out of scope pending curator review policy. |
