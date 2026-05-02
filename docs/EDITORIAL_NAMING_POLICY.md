# Editorial Naming Policy

Canonical names are display labels for Detour. They should be readable to a traveler while preserving all sourced variants in field provenance. A canonical name decision does not delete, rewrite, or demote the source record; non-canonical names remain visible as alternate sourced values.

## Rules

1. Common person-name building form is canonical.
   When NRHP uses register order such as `Last, First, House` and OSM or another local source uses `First Last House`, the common display form is canonical. The NRHP register form remains an alternate sourced name because it is useful for audit, citation, and search.

2. Accented local spelling is canonical when sourced.
   If any source carries the accented form, use that spelling for display, for example `El Zaguán`. Unaccented source forms remain alternates. This keeps local orthography visible without hiding ASCII-only source records.

3. Drop leading articles unless they are integral.
   Prefer `Santa Fe Plaza` over `The Santa Fe Plaza` unless the article is part of a legal, historic, or branded name. Article variants remain alternates for search and provenance.

4. Prefer plain proper names over parenthetical labels.
   Use `Fort Marcy Ruins` rather than `Fort Marcy (ruins)` when a sourced proper-name form exists. Parenthetical labels are retained as alternates when they came from a source.

5. Use the more specific common civic/infrastructure name when it disambiguates.
   For bridges and similar civic assets, keep the street-specific common name when it improves recognition, for example `Don Gaspar Avenue Bridge`; preserve the shorter register name as an alternate.

## Admin Display

The admin viewer should show the canonical value as the highlighted value for each field and list all alternate sourced values below it. Name conflicts caused only by register order, accents, articles, or parenthetical normalization are still conflicts, but they should be treated as resolved normalization cases once exactly one provenance row is marked canonical.
