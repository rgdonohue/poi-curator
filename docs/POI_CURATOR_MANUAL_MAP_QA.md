# POI Curator Manual Map QA

Use this for a short product-legibility pass in `/map-test` while history scoring changes are frozen.

Goal: confirm that the map UI tells the right place-story for each case. Judge what the tester can see: result names, map placement, route relevance, and whether the list feels obviously on-topic.

## Quick Pass

- Open `/map-test`.
- Leave `Raw scores` off for the main pass.
- For nearby cases, judge the top 3 results first, then scan the rest.
- For route cases, check both the list and whether result pins stay plausibly close to the drawn route.
- Do not block on small ordering swaps when the visible story is still correct.

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

Acceptable behavior:

- `Acequia Madre` appears, even if it is the only result.
- One or two clearly water-linked corridor results.
- Tight result set that feels intentionally narrow rather than incomplete.

Suspicious but not blocking:

- The list is very thin and the water story is only partly legible.
- A generic civic item appears alongside `Acequia Madre`, but the water interpretation still dominates.
- `Acequia Trail Crossing` appears without `Acequia Madre`, if the overall corridor still reads as water-linked.

Blocking behavior:

- Water theme is not legible at all.
- Plaza or broad downtown history anchors appear.
- The result set reads as generic civic browsing rather than acequia-linked water traces.

## Severity Guide

Acceptable means the tester would still understand the intended story without explanation.

Suspicious but not blocking means the visible story is mostly right, but ranking or framing feels soft enough that it should be noted for follow-up.

Blocking means the visible story is wrong, off-topic, empty when it should not be, or disconnected enough from the map context that a user would lose trust.
