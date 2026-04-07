const SANTA_FE_CENTER = [-105.9378, 35.687];
const DEFAULT_ZOOM = 13.2;
const REGION_HINT = "santa-fe";
const EMPTY_COLLECTION = { type: "FeatureCollection", features: [] };

const LOCATION_PRESETS = [
  { name: "Plaza", coordinates: [-105.9378, 35.687] },
  { name: "Railyard", coordinates: [-105.9521, 35.6815] },
  { name: "Canyon Road", coordinates: [-105.9169, 35.6848] },
  { name: "Acequia Corridor", coordinates: [-105.9334, 35.6829] },
];

const ROUTE_SAMPLES = [
  {
    name: "Plaza",
    coordinates: [
      [-105.9402, 35.6845],
      [-105.9379, 35.687],
      [-105.9346, 35.6887],
    ],
  },
  {
    name: "Railyard",
    coordinates: [
      [-105.955, 35.679],
      [-105.952, 35.6807],
      [-105.948, 35.6835],
    ],
  },
  {
    name: "Canyon Road",
    coordinates: [
      [-105.919, 35.6838],
      [-105.9173, 35.6845],
      [-105.9155, 35.6852],
    ],
  },
  {
    name: "Acequia Corridor",
    coordinates: [
      [-105.936, 35.6815],
      [-105.9339, 35.6822],
      [-105.931, 35.684],
    ],
  },
];

const fallbackCategories = [
  { slug: "history", label: "History" },
  { slug: "culture", label: "Culture" },
  { slug: "art", label: "Art" },
  { slug: "scenic", label: "Scenic" },
  { slug: "food", label: "Food" },
  { slug: "civic", label: "Civic / Infrastructure" },
  { slug: "mixed", label: "Mixed" },
];

const state = {
  mode: "nearby",
  categories: [],
  config: null,
  center: null,
  routePoints: [],
  routeLabel: "",
  results: [],
  resultsById: new Map(),
  selectedResultId: null,
  selectedPoiDetail: null,
  currentPayload: null,
  mapReady: false,
  map: null,
  nearbyMarker: null,
  routeStartMarker: null,
  routeEndMarker: null,
  resultPopup: null,
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  initPresetButtons();
  initRouteSampleSelect();
  initMap();
  void loadBootData();
});

function cacheElements() {
  els.categorySelect = document.getElementById("category-select");
  els.themeSelect = document.getElementById("theme-select");
  els.travelModeSelect = document.getElementById("travel-mode-select");
  els.limitInput = document.getElementById("limit-input");
  els.radiusInput = document.getElementById("radius-input");
  els.maxDetourInput = document.getElementById("max-detour-input");
  els.sampleRouteSelect = document.getElementById("sample-route-select");
  els.loadRouteButton = document.getElementById("load-route-button");
  els.undoRoutePointButton = document.getElementById("undo-route-point-button");
  els.runQueryButton = document.getElementById("run-query-button");
  els.copyPayloadButton = document.getElementById("copy-payload-button");
  els.resetButton = document.getElementById("reset-button");
  els.resultCount = document.getElementById("result-count");
  els.resultsList = document.getElementById("results-list");
  els.querySummary = document.getElementById("query-summary");
  els.detailEmpty = document.getElementById("detail-empty");
  els.detailContent = document.getElementById("detail-content");
  els.showRawToggle = document.getElementById("show-raw-toggle");
  els.statusPill = document.getElementById("status-pill");
  els.statusDot  = document.getElementById("status-dot");
  els.nearbyControls = document.getElementById("nearby-controls");
  els.routeControls = document.getElementById("route-controls");
  els.nearbyCenterReadout = document.getElementById("nearby-center-readout");
  els.routeSummary = document.getElementById("route-summary");
  els.extraMinutesReadout = document.getElementById("extra-minutes-readout");
  els.mapInstruction = document.getElementById("map-instruction");
}

function bindEvents() {
  document.querySelectorAll('input[name="mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.mode = input.value;
      renderMode();
      updateMarkers();
      renderStatusInstruction();
    });
  });

  els.travelModeSelect.addEventListener("change", () => {
    applyTravelDefaults();
    renderRouteSummary();
  });

  els.loadRouteButton.addEventListener("click", () => {
    loadSelectedSampleRoute();
  });

  els.maxDetourInput.addEventListener("input", () => {
    els.maxDetourInput.dataset.userEdited = "true";
  });

  els.undoRoutePointButton.addEventListener("click", () => {
    if (!state.routePoints.length) {
      setStatus("Route has no points to remove.");
      return;
    }
    state.routePoints.pop();
    state.routeLabel = state.routeLabel || "Manual route";
    updateRouteGeometry();
    renderRouteSummary();
    updateMarkers();
    setStatus("Removed the last route point.");
  });

  els.runQueryButton.addEventListener("click", () => {
    void runQuery();
  });

  els.copyPayloadButton.addEventListener("click", () => {
    void copyPayload();
  });

  els.resetButton.addEventListener("click", () => {
    resetInterface();
  });

  els.showRawToggle.addEventListener("change", () => {
    renderResults();
    renderDetail();
  });
}

async function loadBootData() {
  await Promise.all([loadConfig(), loadCategories()]);
  applyTravelDefaults();
  renderMode();
  renderNearbyCenter();
  renderRouteSummary();
  renderResults();
  renderDetail();
  setStatus("Ready.");
}

async function loadConfig() {
  try {
    const response = await fetch("/v1/config");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(readApiError(payload));
    }
    state.config = payload;
  } catch (error) {
    state.config = {
      default_detour_budgets_by_mode: {
        driving: { max_detour_meters: 1600, max_extra_minutes: 8 },
        walking: { max_detour_meters: 350, max_extra_minutes: 6 },
      },
    };
    setStatus(`Config fallback in use: ${error.message}`);
  }
}

async function loadCategories() {
  try {
    const response = await fetch("/v1/categories");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(readApiError(payload));
    }
    state.categories = ensureMixedCategory(payload);
  } catch (error) {
    state.categories = fallbackCategories;
    setStatus(`Category fallback in use: ${error.message}`);
  }
  populateCategories();
}

function initPresetButtons() {
  const container = document.getElementById("nearby-preset-row");
  LOCATION_PRESETS.forEach((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "preset-button";
    button.textContent = preset.name;
    button.addEventListener("click", () => {
      state.center = [...preset.coordinates];
      state.mode = "nearby";
      setSelectedMode("nearby");
      renderMode();
      renderNearbyCenter();
      updateMarkers();
      flyToCoordinate(state.center);
      setStatus(`Nearby center set to ${preset.name}.`);
    });
    container.appendChild(button);
  });
}

function initRouteSampleSelect() {
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose a sample route";
  els.sampleRouteSelect.appendChild(placeholder);

  ROUTE_SAMPLES.forEach((sample) => {
    const option = document.createElement("option");
    option.value = sample.name;
    option.textContent = sample.name;
    els.sampleRouteSelect.appendChild(option);
  });
}

function populateCategories() {
  const current = els.categorySelect.value || "mixed";
  els.categorySelect.innerHTML = "";
  state.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.slug;
    option.textContent = category.label;
    els.categorySelect.appendChild(option);
  });
  els.categorySelect.value = state.categories.some((item) => item.slug === current)
    ? current
    : "mixed";
}

function initMap() {
  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        carto: {
          type: "raster",
          tiles: [
            "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
            "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
            "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
            "https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
          ],
          tileSize: 512,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        },
      },
      layers: [
        {
          id: "carto",
          type: "raster",
          source: "carto",
        },
      ],
    },
    center: SANTA_FE_CENTER,
    zoom: DEFAULT_ZOOM,
  });

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.on("load", () => {
    state.mapReady = true;
    addMapLayers(map);
    map.on("click", "results-circles", (event) => {
      const poiId = event.features?.[0]?.properties?.poiId;
      if (poiId) {
        void selectResult(poiId, { flyTo: false });
      }
    });
    map.on("mouseenter", "results-circles", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "results-circles", () => {
      map.getCanvas().style.cursor = "";
    });
    updateRouteGeometry();
    updateResultLayers();
    updateMarkers();
  });
  map.on("click", (event) => {
    if (map.queryRenderedFeatures(event.point, { layers: ["results-circles"] }).length) {
      return;
    }
    handleMapClick(event.lngLat.lng, event.lngLat.lat);
  });
  state.map = map;
}

function addMapLayers(map) {
  map.addSource("route-line", { type: "geojson", data: EMPTY_COLLECTION });
  map.addSource("route-vertices", { type: "geojson", data: EMPTY_COLLECTION });
  map.addSource("results", { type: "geojson", data: EMPTY_COLLECTION });
  map.addSource("selected-result", { type: "geojson", data: EMPTY_COLLECTION });

  map.addLayer({
    id: "route-line-layer",
    type: "line",
    source: "route-line",
    paint: {
      "line-color": "#7C3AED",
      "line-width": 3,
      "line-opacity": 0.85,
    },
  });
  map.addLayer({
    id: "route-vertices-layer",
    type: "circle",
    source: "route-vertices",
    paint: {
      "circle-radius": 5,
      "circle-color": "#7C3AED",
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: "results-circles",
    type: "circle",
    source: "results",
    paint: {
      "circle-radius": 6,
      "circle-color": "#2563EB",
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: "selected-result-circle",
    type: "circle",
    source: "selected-result",
    paint: {
      "circle-radius": 10,
      "circle-color": "#F59E0B",
      "circle-stroke-color": "#0F172A",
      "circle-stroke-width": 2.5,
    },
  });
}

function handleMapClick(lng, lat) {
  const coordinates = [roundCoordinate(lng), roundCoordinate(lat)];
  if (state.mode === "nearby") {
    state.center = coordinates;
    renderNearbyCenter();
    updateMarkers();
    setStatus(`Nearby center set at ${formatCoordinatePair(coordinates)}.`);
    return;
  }

  state.routePoints = [...state.routePoints, coordinates];
  state.routeLabel = "Manual route";
  updateRouteGeometry();
  renderRouteSummary();
  updateMarkers();
  setStatus(`Added route point ${state.routePoints.length}.`);
}

function renderMode() {
  const isNearby = state.mode === "nearby";
  els.nearbyControls.classList.toggle("hidden", !isNearby);
  els.routeControls.classList.toggle("hidden", isNearby);
  els.mapInstruction.textContent = isNearby
    ? "Nearby mode: click the map to set the query center."
    : "Route mode: click the map to add route vertices or load a sample route.";
  syncRouteLayerVisibility();
  updateMarkers();
}

function renderStatusInstruction() {
  if (state.mode === "nearby" && !state.center) {
    setStatus("Select a nearby center on the map.");
  } else if (state.mode === "route" && state.routePoints.length < 2) {
    setStatus("Add at least 2 route points or load a sample route.");
  }
}

function applyTravelDefaults() {
  const mode = els.travelModeSelect.value;
  const defaults = state.config?.default_detour_budgets_by_mode?.[mode];
  const defaultDetour =
    defaults?.max_detour_meters ?? (mode === "walking" ? 350 : 1600);
  const extraMinutes =
    defaults?.max_extra_minutes ?? (mode === "walking" ? 6 : 8);

  els.extraMinutesReadout.textContent = `${extraMinutes} min auto`;
  if (!els.maxDetourInput.dataset.userEdited) {
    els.maxDetourInput.value = String(defaultDetour);
  }
}

function loadSelectedSampleRoute() {
  const sample = ROUTE_SAMPLES.find((item) => item.name === els.sampleRouteSelect.value);
  if (!sample) {
    setStatus("Choose a sample route first.");
    return;
  }
  state.mode = "route";
  setSelectedMode("route");
  state.routeLabel = sample.name;
  state.routePoints = sample.coordinates.map((point) => [...point]);
  renderMode();
  updateRouteGeometry();
  renderRouteSummary();
  updateMarkers();
  fitCoordinates(state.routePoints);
  setStatus(`Loaded ${sample.name} sample route.`);
}

function renderNearbyCenter() {
  els.nearbyCenterReadout.textContent = state.center
    ? formatCoordinatePair(state.center)
    : "No center selected";
}

function renderRouteSummary() {
  if (!state.routePoints.length) {
    els.routeSummary.textContent = "Add at least 2 route points";
    return;
  }
  const start = formatCoordinatePair(state.routePoints[0]);
  const end = formatCoordinatePair(state.routePoints[state.routePoints.length - 1]);
  els.routeSummary.textContent = `${state.routePoints.length} points | ${start} -> ${end}`;
}

function updateRouteGeometry() {
  if (!state.mapReady) {
    return;
  }
  const lineSource = state.map.getSource("route-line");
  const vertexSource = state.map.getSource("route-vertices");
  lineSource.setData(
    state.routePoints.length >= 2
      ? {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: state.routePoints,
              },
              properties: {},
            },
          ],
        }
      : EMPTY_COLLECTION,
  );
  vertexSource.setData({
    type: "FeatureCollection",
    features: state.routePoints.map((coordinates, index) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates },
      properties: { index },
    })),
  });
  syncRouteLayerVisibility();
}

function syncRouteLayerVisibility() {
  if (!state.mapReady) {
    return;
  }
  const visibility = state.mode === "route" ? "visible" : "none";
  state.map.setLayoutProperty("route-line-layer", "visibility", visibility);
  state.map.setLayoutProperty("route-vertices-layer", "visibility", visibility);
}

function updateMarkers() {
  if (!state.mapReady) {
    return;
  }

  if (state.mode === "nearby" && state.center) {
    state.nearbyMarker =
      state.nearbyMarker || new maplibregl.Marker({ element: createMarkerElement("nearby-marker") });
    state.nearbyMarker.setLngLat(state.center).addTo(state.map);
  } else if (state.nearbyMarker) {
    state.nearbyMarker.remove();
  }

  if (state.mode === "route" && state.routePoints.length) {
    const startPoint = state.routePoints[0];
    state.routeStartMarker =
      state.routeStartMarker ||
      new maplibregl.Marker({ element: createMarkerElement("route-marker") });
    state.routeStartMarker.setLngLat(startPoint).addTo(state.map);

    if (state.routePoints.length >= 2) {
      const endPoint = state.routePoints[state.routePoints.length - 1];
      state.routeEndMarker =
        state.routeEndMarker ||
        new maplibregl.Marker({ element: createMarkerElement("route-marker") });
      state.routeEndMarker.setLngLat(endPoint).addTo(state.map);
    } else if (state.routeEndMarker) {
      state.routeEndMarker.remove();
    }
  } else {
    if (state.routeStartMarker) {
      state.routeStartMarker.remove();
    }
    if (state.routeEndMarker) {
      state.routeEndMarker.remove();
    }
  }
}

function createMarkerElement(className) {
  const element = document.createElement("div");
  element.className = className;
  return element;
}

async function runQuery() {
  let payload;
  try {
    payload = buildPayload();
  } catch (error) {
    setStatus(error.message);
    return;
  }

  state.currentPayload = payload;
  const endpoint = state.mode === "nearby" ? "/v1/nearby/suggest" : "/v1/route/suggest";

  els.runQueryButton.disabled = true;
  setStatus(`Querying ${state.mode} suggestions...`);

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(readApiError(result));
    }

    state.results = result.results ?? [];
    state.resultsById = new Map(state.results.map((item) => [item.poi_id, item]));
    state.selectedResultId = null;
    state.selectedPoiDetail = null;
    updateResultLayers();
    renderQuerySummary(result.query_summary);
    renderResults();
    renderDetail();

    if (state.results.length) {
      fitResultsWithContext();
      await selectResult(state.results[0].poi_id, { flyTo: false });
      setStatus(`Loaded ${state.results.length} result${state.results.length === 1 ? "" : "s"}.`);
    } else {
      closePopup();
      setStatus("Query returned no results.");
    }
  } catch (error) {
    clearResults();
    setStatus(`Query failed: ${error.message}`);
  } finally {
    els.runQueryButton.disabled = false;
  }
}

function buildPayload() {
  const theme = els.themeSelect.value || null;
  const limit = clampNumber(els.limitInput.value, 1, 20, 8);
  const travelMode = els.travelModeSelect.value;
  const category = els.categorySelect.value || "mixed";

  if (state.mode === "nearby") {
    if (!state.center) {
      throw new Error("Nearby mode needs a map click or preset center.");
    }
    return {
      center: {
        lat: state.center[1],
        lon: state.center[0],
      },
      travel_mode: travelMode,
      category,
      theme,
      radius_meters: clampNumber(els.radiusInput.value, 50, 10000, 900),
      region_hint: REGION_HINT,
      limit,
    };
  }

  if (state.routePoints.length < 2) {
    throw new Error("Route mode needs at least 2 route points.");
  }

  const routeName = state.routeLabel || "Manual route";
  return {
    route_geometry: {
      type: "LineString",
      coordinates: state.routePoints,
    },
    origin: {
      name: `${routeName} start`,
      coordinates: state.routePoints[0],
    },
    destination: {
      name: `${routeName} end`,
      coordinates: state.routePoints[state.routePoints.length - 1],
    },
    travel_mode: travelMode,
    category,
    theme,
    max_detour_meters: clampNumber(els.maxDetourInput.value, 50, 20000, 800),
    max_extra_minutes: getExtraMinutes(travelMode),
    region_hint: REGION_HINT,
    limit,
  };
}

function getExtraMinutes(travelMode) {
  const defaults = state.config?.default_detour_budgets_by_mode?.[travelMode];
  return defaults?.max_extra_minutes ?? (travelMode === "walking" ? 6 : 8);
}

async function copyPayload() {
  let payload;
  try {
    payload = buildPayload();
  } catch (error) {
    setStatus(error.message);
    return;
  }

  const serialized = JSON.stringify(payload, null, 2);
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(serialized);
      setStatus("Copied payload to clipboard.");
      return;
    } catch {
      // Fall through to execCommand fallback (non-secure context or focus loss).
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = serialized;
  textarea.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(textarea);
  setStatus(ok ? "Copied payload to clipboard." : "Clipboard copy failed — try HTTPS or focus the page.");
}

function renderQuerySummary(summary) {
  if (!summary) {
    els.querySummary.textContent = "No query submitted yet.";
    return;
  }

  const pieces = [
    state.mode,
    summary.travel_mode,
    summary.category,
    summary.theme || "no theme",
  ];
  if (state.mode === "nearby") {
    pieces.push(`${summary.radius_meters}m radius`);
  } else {
    pieces.push(`${summary.max_detour_meters}m detour`);
  }
  pieces.push(`${state.results.length} result${state.results.length === 1 ? "" : "s"}`);
  els.querySummary.textContent = pieces.join(" | ");
}

function clearResults() {
  state.results = [];
  state.resultsById = new Map();
  state.selectedResultId = null;
  state.selectedPoiDetail = null;
  updateResultLayers();
  renderQuerySummary(null);
  renderResults();
  renderDetail();
  closePopup();
}

function renderResults() {
  els.resultCount.textContent = String(state.results.length);
  els.resultsList.innerHTML = "";

  if (!state.results.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <div class="skeleton-preview">
        <div class="skeleton-preview-header">
          <div class="skeleton-bone" style="width: 48%; height: 13px;"></div>
          <div class="skeleton-bone" style="width: 16%; height: 13px;"></div>
        </div>
        <div class="skeleton-bone" style="width: 32%; height: 9px;"></div>
        <div class="skeleton-bone" style="width: 86%; height: 9px; margin-top: 8px;"></div>
        <div class="skeleton-bone" style="width: 68%; height: 9px;"></div>
      </div>
      <p class="empty-label">No results to inspect.</p>
    `;
    els.resultsList.appendChild(empty);
    return;
  }

  state.results.forEach((result) => {
    const card = document.createElement("article");
    card.className = `result-card${result.poi_id === state.selectedResultId ? " is-selected" : ""}`;
    card.innerHTML = buildResultCardMarkup(result);
    card.addEventListener("click", () => {
      void selectResult(result.poi_id, { flyTo: true });
    });
    els.resultsList.appendChild(card);
  });
}

function buildResultCardMarkup(result) {
  const explanation = result.why_it_matters?.[0] || result.short_description || "No explanation";
  const breakdownSummary = formatBreakdownSummary(result.score_breakdown);
  const rawBreakdown = els.showRawToggle.checked
    ? `<pre class="raw-breakdown">${escapeHtml(
        JSON.stringify(result.score_breakdown || {}, null, 2),
      )}</pre>`
    : "";

  return `
    <div class="result-card-header">
      <h3>${escapeHtml(result.name)}</h3>
      <div class="result-score">${formatScore(result.score)}</div>
    </div>
    <div class="result-meta">
      <span class="meta-chip">${escapeHtml(result.primary_category)}</span>
      ${result.category_match_type ? `<span class="meta-chip">${escapeHtml(result.category_match_type)}</span>` : ""}
      ${renderBadgeMarkup(result.badges)}
    </div>
    <div class="result-snippet">${escapeHtml(explanation)}</div>
    <div class="result-distance">${escapeHtml(formatDistanceText(result))}</div>
    <div class="result-distance">${escapeHtml(breakdownSummary)}</div>
    ${rawBreakdown}
  `;
}

function renderBadgeMarkup(badges) {
  return (badges || [])
    .slice(0, 3)
    .map((badge) => `<span class="badge-chip">${escapeHtml(badge)}</span>`)
    .join("");
}

async function selectResult(poiId, options = { flyTo: true }) {
  const result = state.resultsById.get(poiId);
  if (!result) {
    return;
  }

  state.selectedResultId = poiId;
  state.selectedPoiDetail = null;
  updateSelectedResultLayer();
  renderResults();
  renderDetail();
  openPopup(result);

  if (options.flyTo) {
    state.map.flyTo({
      center: result.coordinates,
      zoom: Math.max(state.map.getZoom(), 14.2),
      essential: true,
    });
  }

  try {
    const response = await fetch(`/v1/poi/${encodeURIComponent(poiId)}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(readApiError(payload));
    }
    if (state.selectedResultId === poiId) {
      state.selectedPoiDetail = payload;
      renderDetail();
    }
  } catch (error) {
    if (state.selectedResultId === poiId) {
      setStatus(`Detail fetch failed for ${result.name}: ${error.message}`);
    }
  }
}

function renderDetail() {
  const result = state.selectedResultId ? state.resultsById.get(state.selectedResultId) : null;
  if (!result) {
    els.detailEmpty.classList.remove("hidden");
    els.detailContent.classList.add("hidden");
    els.detailContent.innerHTML = "";
    return;
  }

  els.detailEmpty.classList.add("hidden");
  els.detailContent.classList.remove("hidden");
  els.detailContent.innerHTML = buildDetailMarkup(result, state.selectedPoiDetail);
}

function buildDetailMarkup(result, detail) {
  const whyItMatters = (detail?.why_it_matters || result.why_it_matters || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const badges = renderChipMarkup(detail?.badges || result.badges, "badge-chip");
  const themes = renderThemeMarkup(detail?.themes || []);
  const rawBreakdown = els.showRawToggle.checked
    ? `<pre class="raw-breakdown">${escapeHtml(
        JSON.stringify(result.score_breakdown || {}, null, 2),
      )}</pre>`
    : "";

  return `
    <div class="detail-header-row">
      <h3>${escapeHtml(result.name)}</h3>
      <div class="result-score">${formatScore(result.score)}</div>
    </div>
    <div class="detail-meta">
      <span class="meta-chip">${escapeHtml(result.primary_category)}</span>
      ${result.category_match_type ? `<span class="meta-chip">${escapeHtml(result.category_match_type)}</span>` : ""}
      <span class="meta-chip">${escapeHtml(formatDistanceText(result))}</span>
    </div>
    <div class="detail-text">${escapeHtml(detail?.short_description || result.short_description)}</div>
    <div class="chip-row">${badges}</div>
    ${themes ? `<div class="chip-row">${themes}</div>` : ""}
    <ul class="detail-list">${whyItMatters || "<li>No explanation returned.</li>"}</ul>
    <div class="detail-text">${escapeHtml(formatBreakdownSummary(result.score_breakdown))}</div>
    ${rawBreakdown}
  `;
}

function renderChipMarkup(items, className) {
  return (items || [])
    .map((item) => `<span class="${className}">${escapeHtml(item)}</span>`)
    .join("");
}

function renderThemeMarkup(themes) {
  return themes
    .slice(0, 4)
    .map(
      (theme) =>
        `<span class="theme-chip">${escapeHtml(theme.label)} (${escapeHtml(theme.status)})</span>`,
    )
    .join("");
}

function updateResultLayers() {
  if (!state.mapReady) {
    return;
  }

  const resultsSource = state.map.getSource("results");
  resultsSource.setData({
    type: "FeatureCollection",
    features: state.results.map((item) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: item.coordinates,
      },
      properties: {
        poiId: item.poi_id,
        name: item.name,
        score: formatScore(item.score),
      },
    })),
  });
  updateSelectedResultLayer();
}

function updateSelectedResultLayer() {
  if (!state.mapReady) {
    return;
  }

  const selectedSource = state.map.getSource("selected-result");
  const result = state.selectedResultId ? state.resultsById.get(state.selectedResultId) : null;
  selectedSource.setData(
    result
      ? {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Point", coordinates: result.coordinates },
              properties: {},
            },
          ],
        }
      : EMPTY_COLLECTION,
  );
}

function openPopup(result) {
  closePopup();
  state.resultPopup = new maplibregl.Popup({ closeButton: true, closeOnClick: false })
    .setLngLat(result.coordinates)
    .setHTML(
      `<p class="popup-title">${escapeHtml(result.name)}</p>` +
      `<p class="popup-copy">${escapeHtml(formatScore(result.score))} · ${escapeHtml(formatDistanceText(result))}</p>`,
    )
    .addTo(state.map);
}

function closePopup() {
  if (state.resultPopup) {
    state.resultPopup.remove();
    state.resultPopup = null;
  }
}

function fitResultsWithContext() {
  const coordinates = [];
  if (state.mode === "nearby" && state.center) {
    coordinates.push(state.center);
  }
  if (state.mode === "route") {
    coordinates.push(...state.routePoints);
  }
  coordinates.push(...state.results.map((item) => item.coordinates));
  if (coordinates.length) {
    fitCoordinates(coordinates);
  }
}

function fitCoordinates(coordinates) {
  if (!state.mapReady || !coordinates.length) {
    return;
  }

  const bounds = new maplibregl.LngLatBounds(coordinates[0], coordinates[0]);
  coordinates.slice(1).forEach((point) => bounds.extend(point));
  state.map.fitBounds(bounds, {
    padding: { top: 60, right: 60, bottom: 60, left: 60 },
    maxZoom: 15.2,
    duration: 700,
  });
}

function flyToCoordinate(coordinates) {
  if (!state.mapReady) {
    return;
  }
  state.map.flyTo({ center: coordinates, zoom: Math.max(state.map.getZoom(), 14) });
}

function resetInterface() {
  state.mode = "nearby";
  state.center = null;
  state.routePoints = [];
  state.routeLabel = "";
  state.currentPayload = null;
  setSelectedMode("nearby");
  els.categorySelect.value = state.categories.some((item) => item.slug === "mixed")
    ? "mixed"
    : state.categories[0]?.slug || "";
  els.themeSelect.value = "";
  els.travelModeSelect.value = "walking";
  els.radiusInput.value = "900";
  els.limitInput.value = "8";
  delete els.maxDetourInput.dataset.userEdited;
  applyTravelDefaults();
  els.sampleRouteSelect.value = "";
  clearResults();
  updateRouteGeometry();
  renderMode();
  renderNearbyCenter();
  renderRouteSummary();
  updateMarkers();
  if (state.mapReady) {
    state.map.flyTo({ center: SANTA_FE_CENTER, zoom: DEFAULT_ZOOM });
  }
  setStatus("Reset map tester.");
}

function setSelectedMode(mode) {
  document.querySelectorAll('input[name="mode"]').forEach((input) => {
    input.checked = input.value === mode;
  });
}

function setStatus(message) {
  els.statusPill.textContent = message;
  const lower = message.toLowerCase();
  const isError   = lower.includes("fail") || lower.includes("error") || lower.includes("need");
  const isActive  = lower.includes("query") || lower.includes("load");
  const isOk      = lower.includes("loaded") || lower.includes("copied") || lower.includes("ready") || lower.includes("reset");
  els.statusDot.className = "status-dot" +
    (isError  ? " is-error"  :
     isOk     ? " is-ok"     :
     isActive ? " is-active" : "");
}

function formatDistanceText(result) {
  if (typeof result.distance_from_center_meters === "number") {
    return `${result.distance_from_center_meters}m from center | ${result.estimated_access_minutes} min access`;
  }
  return `${result.distance_from_route_m}m from route | ${result.estimated_extra_minutes} min extra`;
}

function formatBreakdownSummary(breakdown) {
  if (!breakdown || !Object.keys(breakdown).length) {
    return "No score breakdown returned.";
  }
  const parts = Object.entries(breakdown)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${Number(value).toFixed(2)}`);
  return `Breakdown: ${parts.join(", ")}`;
}

function formatScore(score) {
  return `Score ${Number(score).toFixed(2)}`;
}

function formatCoordinatePair(coordinates) {
  return `${coordinates[1].toFixed(5)}, ${coordinates[0].toFixed(5)}`;
}

function roundCoordinate(value) {
  return Math.round(value * 1e6) / 1e6;
}

function clampNumber(value, min, max, fallback) {
  const number = Number.parseInt(value, 10);
  if (Number.isNaN(number)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, number));
}

function ensureMixedCategory(categories) {
  const normalized = categories.map((item) => ({
    slug: item.slug,
    label: item.label || titleCase(item.slug),
  }));
  if (!normalized.some((item) => item.slug === "mixed")) {
    normalized.push({ slug: "mixed", label: "Mixed" });
  }
  return normalized;
}

function titleCase(value) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function readApiError(payload) {
  if (!payload) {
    return "Unknown API error";
  }
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => item.msg || item.message || JSON.stringify(item))
      .join("; ");
  }
  return typeof payload === "string" ? payload : JSON.stringify(payload);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
