# POI Curator Manual Map QA

Use this for a short product-legibility pass in `/map-test` while history scoring changes are frozen.

Goal: confirm that the map UI tells the right place-story for each case. Judge what the tester can see: result names, map placement, route relevance, and whether the list feels obviously on-topic.

This pass is now explicitly geometry-aware. Do not only judge whether the returned place is thematically relevant. Also judge whether the visible pin placement feels like a believable encounter location for that place.

## Quick Pass

- Open `/map-test`.
- Leave `Raw scores` off for the main pass.
- For nearby cases, judge the top 3 results first, then scan the rest.
- For route cases, check both the list and whether result pins stay plausibly close to the drawn route.
- Do not block on small ordering swaps when the visible story is still correct.

## Geometry-Aware Checks

Apply these checks during the pass, especially for corridor-like cases:

- When the top result is corridor-like, ask whether the returned pin feels like a plausible encounter location rather than an abstract midpoint.
- For `nearby-acequia-water`, rerun the query after moving the center slightly west, east, north, and south. The top pin should shift plausibly along or around the corridor rather than snapping back to a fixed abstract center.
- For `route-acequia-water`, ask whether the returned pin sits near the relevant segment of the route rather than a remote part of the corridor.
- For point-like building results, confirm they still behave like ordinary POIs: one stable point, no corridor-like drift, no odd area-style interpretation.
- If a result feels thematically correct but spatially arbitrary, mark it `Suspicious` rather than `Pass`.

## Case 1: Nearby Plaza-Core History

Case id: `nearby-plaza-history`

Setup: `Nearby` | preset `Plaza` | category `History` | theme `None` | travel mode `Walking` | radius `800` | limit `5`

Expected good behavior:

- The list should feel unmistakably like plaza-core history, not generic downtown browsing.
- Strong plaza anchors should appear immediately. `Palace of the Governors` should be present, and `The Santa Fe Plaza` is a valid supporting result.
- Other acceptable historical anchors include `Soldiers' Monument`, `Loretto Chapel`, `New Mexico History Museum`, and `Museum of Contemporary Native Arts`.
- Pins should cluster around the plaza core and nearby historic blocks.

Acceptable behavior:

- At least 3 clearly plaza-core historical results.
- Minor order changes among the main anchors.
- One civic-context result, such as `The Santa Fe Plaza`, mixed into otherwise history-led results.

Suspicious but not blocking:

- The list is still downtown-historic, but one weaker or more generic downtown item rises above a stronger anchor.
- `Palace of the Governors` is present but unexpectedly low.
- One result lands a bit outside the tight plaza core while the overall list still reads as correct.

Blocking behavior:

- The list reads as generic downtown search instead of historic-center search.
- Core anchors are missing entirely.
- Clearly off-topic commercial results appear, especially `Santa Fe Farmers Market`.
- The map returns empty or results are visibly far from the plaza core.

## Case 2: Route Historic-Center Driving

Case id: `route-historic-center-driving`

Setup: `Route` | draw a short southwest-to-northeast route through the historic center, passing the San Miguel / De Vargas area toward the plaza edge | category `History` | theme `None` | travel mode `Driving` | max detour `1800` | limit `5`

Expected good behavior:

- The list should be led by major historic-center anchors that make sense for a short driving detour.
- `De Vargas Street House` should be highly visible. `San Miguel Chapel` is a valid top-tier result even though it presents as culture-adjacent.
- Other strong supporting results include `Digneo-Valdes House`, `Gregorio Crespin House`, and `Kruger Building`.
- Pins should stay plausibly close to the route and feel drivable without obvious route-breaking detours.

Acceptable behavior:

- At least 3 strong historic-center results near the route.
- Small reshuffling among the main historic houses and chapel.
- One culture-adjacent historic landmark in the top group if the route story still reads as historic-center.

Suspicious but not blocking:

- The route is still clearly historic-center, but one generic downtown result sneaks into the top few.
- The best anchor is present but not near the top.
- One result asks for a detour that feels a bit long relative to the rest.

Blocking behavior:

- The list does not feel route-relevant to the historic center.
- The top results ignore the San Miguel / De Vargas / plaza area.
- Clearly off-topic downtown results appear, especially `Santa Fe Farmers Market`.
- Results are visibly disconnected from the route line or the list turns into generic civic browsing.

## Case 3: Nearby Railyard Rail

Case id: `nearby-railyard-rail`

Setup: `Nearby` | preset `Railyard` | category `Mixed` | theme `Rail` | travel mode `Walking` | radius `900` | limit `5`

Expected good behavior:

- The list should read as rail-specific, not just general history or downtown civic.
- The two depot anchors should be prominent: `Atchison, Topeka & Santa Fe Railway Depot` and `Denver & Rio Grande Western Railroad Depot`.
- Supporting corridor traces are fine if they still strengthen the rail story, especially `Santa Fe Railyard Park` and `Rail Trail St. Francis Tunnel Grid Vent`.
- Pins should stay in and around the railyard corridor.

Acceptable behavior:

- One or both depot anchors appear in the top few.
- Supporting rail-corridor or repurposed-infrastructure results appear below the depots.
- Small ordering swaps among the two depots and `Railyard Park`.

Suspicious but not blocking:

- The list is still railyard-adjacent, but feels more like generic civic/history than rail.
- Only one depot appears, with the rest being looser corridor results.
- A result is nearby and plausible, but does not immediately communicate a rail reading.

Blocking behavior:

- The rail theme disappears and unrelated downtown anchors dominate.
- Clearly forbidden downtown spillover appears, especially `The Santa Fe Plaza` or `Santa Fe Farmers Market`.
- Results are centered outside the railyard corridor or the list becomes generic mixed downtown content.

## Case 4: Nearby Acequia Water

Case id: `nearby-acequia-water`

Setup: `Nearby` | preset `Acequia Corridor` | category `Mixed` | theme `Water` | travel mode `Walking` | radius `500` | limit `5`

Expected good behavior:

- The list should read as acequia / water infrastructure, not general civic or history.
- `Acequia Madre` is the clearest expected anchor.
- `Acequia Trail Crossing` is also a valid water-linked result.
- A short list, including a single strong result, is acceptable if it is obviously the right water story.
- The returned pin for `Acequia Madre` should feel like a plausible encounter point on or near the acequia corridor.
- Small nearby-center shifts should produce sensible pin shifts rather than a fixed midpoint feel.

Acceptable behavior:

- `Acequia Madre` appears, even if it is the only result.
- One or two clearly water-linked corridor results.
- Tight result set that feels intentionally narrow rather than incomplete.

Suspicious but not blocking:

- The list is very thin and the water story is only partly legible.
- A generic civic item appears alongside `Acequia Madre`, but the water interpretation still dominates.
- `Acequia Trail Crossing` appears without `Acequia Madre`, if the overall corridor still reads as water-linked.
- `Acequia Madre` appears, but the pin still feels arbitrary or visually detached from how a traveler would encounter it.
- The pin moves, but not in a way that tracks the nearby-center shift convincingly.

Blocking behavior:

- Water theme is not legible at all.
- Plaza or broad downtown history anchors appear.
- The result set reads as generic civic browsing rather than acequia-linked water traces.
- The top acequia result is returned, but the pin clearly behaves like an implausible abstract center rather than a believable encounter point.

## Case 5: Route Acequia Water

Case id: `route-acequia-water`

Setup: `Route` | load or draw a short west-to-east route along the acequia corridor | category `Mixed` | theme `Water` | travel mode `Walking` | max detour `600` | limit `5`

Expected good behavior:

- The list should read as acequia / water corridor relevance, not generic civic browsing.
- `Acequia Madre` should be the clearest top-tier result.
- The returned pin should sit near the route-relevant part of the corridor.
- The route and the acequia result should tell one coherent local water story.

Acceptable behavior:

- `Acequia Madre` appears as the main result, even if the list is short.
- `Acequia Trail Crossing` appears as a supporting result.
- The acequia pin is close enough to the route that a user would read it as route-plausible.

Suspicious but not blocking:

- The result list is right, but the acequia pin looks a little detached from the relevant route segment.
- A generic civic result appears below the water-linked result without dominating the story.
- The route reading is mostly right, but the map behavior still feels a bit thin.

Blocking behavior:

- The route results read as generic civic or downtown browsing instead of water-linked corridor behavior.
- `Acequia Madre` is missing with no equally legible water-linked substitute.
- The acequia pin lands in a way that feels visibly disconnected from the relevant route segment.

## Case 6: Negative Control for Ordinary Building-Like POIs

Use this as a regression check after the main cases.

Setup: run either `nearby-plaza-history` or `route-historic-center-driving`, then click one ordinary building-like result such as `De Vargas Street House`, `Gregorio Crespin House`, or `Kruger Building`.

Expected good behavior:

- The selected building still behaves like a normal point-like POI.
- The pin feels stable and ordinary, not corridor-like or area-like.
- Nothing about the result presentation suggests stretched geometry, corridor anchoring, or district-style behavior.

Acceptable behavior:

- Minor pin placement imprecision within the immediate building block.
- Normal variation between nearby and route result emphasis.

Suspicious but not blocking:

- The building pin is plausible, but feels slightly offset in a way worth noting.
- The surrounding list is correct, but one ordinary building result feels less point-like than expected.

Blocking behavior:

- An ordinary building-like result presents as though it were a corridor or area.
- The pin placement visibly drifts or behaves inconsistently when nothing about the place suggests extended geometry.
- The result behavior makes normal building-scale POIs feel less trustworthy.

## Severity Guide

Acceptable means the tester would still understand the intended story without explanation.

Suspicious but not blocking means the visible story is mostly right, but ranking or framing feels soft enough that it should be noted for follow-up.

Blocking means the visible story is wrong, off-topic, empty when it should not be, or disconnected enough from the map context that a user would lose trust.

## Recording Template

Record each case in a short grid so the pass does not turn into vague impressions.

Suggested columns:

- `case_id`
- `status` (`Pass`, `Suspicious`, `Fail`)
- `top_result`
- `pin_behavior`
- `notes`
- `screenshot`

Example:

| case_id | status | top_result | pin_behavior | notes | screenshot |
| --- | --- | --- | --- | --- | --- |
| nearby-acequia-water | Pass | Acequia Madre | Pin shifts plausibly west/east along corridor | Tight list but coherent water story | `qa/nearby-acequia-water-pass.png` |
| route-acequia-water | Suspicious | Acequia Madre | Route-adjacent, but pin feels slightly detached from best segment | Watch if Detour needs primary encounter hint | `qa/route-acequia-water-suspicious.png` |
