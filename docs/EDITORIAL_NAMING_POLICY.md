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

6. GNIS variants are alternates, not automatic display replacements.
   GNIS variant names should be preserved as sourced alternate names for search, provenance, and conflict review. The current GNIS official name can be canonical for GNIS-created POIs, but a reviewed local/common name from OSM, city records, or editorial review should remain canonical when it is clearer for display.

7. OSE acequia and POD labels are provisional source labels.
   Public OSE labels for points of diversion and conveyances should be preserved as source evidence. All-caps names, shorthand labels, and `Point of Diversion - X` names are acceptable for unreviewed canonicals, but reviewed display names should normalize capitalization and avoid adding unpublished steward/local names without explicit permission.

8. HPD State Register names follow the same register-name rule as NRHP.
   HPD workbook names such as `Read, Benjamin M., House` or `Bergere, A. M., House` should remain sourced alternates when OSM, NRHP, or editorial review provides the common display form. HPD suffixes such as `NHL` or register/district qualifiers are provenance cues, not automatic display text, unless the qualifier is needed to distinguish two records.

9. DCA institutional names preserve public-facing museum/site branding.
   DCA source labels should corroborate institution identity, but they should not override a clearer common campus name already used by OSM or editorial review. Parent institution names and campus/site names can both be preserved as alternates; the canonical display should be the visitor-facing name for the specific place.

## Admin Display

The admin viewer should show the canonical value as the highlighted value for each field and list all alternate sourced values below it. Name conflicts caused only by register order, accents, articles, parenthetical normalization, HPD register qualifiers, or DCA parent/campus naming should still be visible, but they can be treated as resolved normalization cases once exactly one provenance row is marked canonical.
