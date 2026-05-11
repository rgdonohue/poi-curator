const ADMIN_KEY_STORAGE = "poiCuratorAdminKey";
const SANTA_FE_CENTER = [-105.9378, 35.687];
const DEFAULT_ZOOM = 12.6;
const EMPTY_COLLECTION = { type: "FeatureCollection", features: [] };
const PAGE_SIZE = 50;
const LOG_PAGE_SIZE = 100;

const state = {
  view: "poi-list",
  categories: [],
  health: null,
  config: null,
  selectedPoi: null,
  poiList: [],
  poiListTotal: 0,
  poiListOffset: 0,
  mapPayload: null,
  queryLogs: [],
  queryLogTotal: 0,
  queryLogOffset: 0,
  conflicts: [],
  coverage: null,
  matchLogs: [],
  expandedLogId: null,
  mapBrowser: null,
  detailMap: null,
  detailMarker: null,
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  updateKeyStatus();
  void boot();
});

function cacheElements() {
  els.navButtons = Array.from(document.querySelectorAll("[data-view]"));
  els.views = {
    "poi-list": document.getElementById("view-poi-list"),
    "poi-detail": document.getElementById("view-poi-detail"),
    "map-browser": document.getElementById("view-map-browser"),
    conflicts: document.getElementById("view-conflicts"),
    coverage: document.getElementById("view-coverage"),
    "match-logs": document.getElementById("view-match-logs"),
    "query-logs": document.getElementById("view-query-logs"),
    status: document.getElementById("view-status"),
  };
  els.healthBadge = document.getElementById("health-badge");
  els.settingsToggle = document.getElementById("settings-toggle");
  els.settingsPanel = document.getElementById("settings-panel");
  els.adminKeyForm = document.getElementById("admin-key-form");
  els.adminKeyInput = document.getElementById("admin-key-input");
  els.clearKeyButton = document.getElementById("clear-key-button");
  els.keyStatus = document.getElementById("key-status");
  els.filterCategory = document.getElementById("filter-category");
  els.poiSearch = document.getElementById("poi-search");
  els.filterReviewState = document.getElementById("filter-review-state");
  els.filterSource = document.getElementById("filter-source");
  els.filterTheme = document.getElementById("filter-theme");
  els.filterThemeMatch = document.getElementById("filter-theme-match");
  els.filterDiagnostics = document.getElementById("filter-diagnostics");
  els.filterOverrides = document.getElementById("filter-overrides");
  els.filterActiveOnly = document.getElementById("filter-active-only");
  els.poiListRefresh = document.getElementById("poi-list-refresh");
  els.poiListStatus = document.getElementById("poi-list-status");
  els.poiListBody = document.getElementById("poi-list-body");
  els.poiListPrev = document.getElementById("poi-list-prev");
  els.poiListNext = document.getElementById("poi-list-next");
  els.poiListPage = document.getElementById("poi-list-page");
  els.mapFilterCategory = document.getElementById("map-filter-category");
  els.mapFilterSearch = document.getElementById("map-filter-search");
  els.mapFilterReviewState = document.getElementById("map-filter-review-state");
  els.mapFilterSource = document.getElementById("map-filter-source");
  els.mapFilterTheme = document.getElementById("map-filter-theme");
  els.mapFilterThemeMatch = document.getElementById("map-filter-theme-match");
  els.mapFilterDiagnostics = document.getElementById("map-filter-diagnostics");
  els.mapFilterOverrides = document.getElementById("map-filter-overrides");
  els.mapFilterActiveOnly = document.getElementById("map-filter-active-only");
  els.mapRefresh = document.getElementById("map-refresh");
  els.mapStatus = document.getElementById("map-status");
  els.poiDetailForm = document.getElementById("poi-detail-form");
  els.poiIdInput = document.getElementById("poi-id-input");
  els.poiDetailContent = document.getElementById("poi-detail-content");
  els.mapDetailPanel = document.getElementById("map-detail-panel");
  els.queryLogRefresh = document.getElementById("query-log-refresh");
  els.queryLogFilters = document.getElementById("query-log-filters");
  els.queryLogStatus = document.getElementById("query-log-status");
  els.queryLogBody = document.getElementById("query-log-body");
  els.queryLogPrev = document.getElementById("query-log-prev");
  els.queryLogNext = document.getElementById("query-log-next");
  els.queryLogPage = document.getElementById("query-log-page");
  els.conflictsRefresh = document.getElementById("conflicts-refresh");
  els.conflictsFilters = document.getElementById("conflicts-filters");
  els.conflictsStatus = document.getElementById("conflicts-status");
  els.conflictsBody = document.getElementById("conflicts-body");
  els.coverageRefresh = document.getElementById("coverage-refresh");
  els.coverageStatus = document.getElementById("coverage-status");
  els.coverageContent = document.getElementById("coverage-content");
  els.matchLogRefresh = document.getElementById("match-log-refresh");
  els.matchLogFilters = document.getElementById("match-log-filters");
  els.matchLogStatus = document.getElementById("match-log-status");
  els.matchLogBody = document.getElementById("match-log-body");
  els.statusRefresh = document.getElementById("status-refresh");
  els.healthRaw = document.getElementById("health-raw");
  els.configRaw = document.getElementById("config-raw");
}

function bindEvents() {
  els.navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      showView(button.dataset.view);
    });
  });

  els.settingsToggle.addEventListener("click", () => {
    els.settingsPanel.classList.toggle("hidden");
  });

  els.adminKeyForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const key = els.adminKeyInput.value.trim();
    if (!key) {
      setKeyMessage("No key entered.");
      return;
    }
    localStorage.setItem(ADMIN_KEY_STORAGE, key);
    els.adminKeyInput.value = "";
    updateKeyStatus();
    void loadPoiList();
    void loadQueryLogs();
    void loadMapPois();
    void loadConflicts();
    void loadCoverage();
    void loadMatchLogs();
  });

  els.clearKeyButton.addEventListener("click", () => {
    localStorage.removeItem(ADMIN_KEY_STORAGE);
    els.adminKeyInput.value = "";
    updateKeyStatus();
    state.poiList = [];
    state.queryLogs = [];
    state.conflicts = [];
    state.coverage = null;
    state.matchLogs = [];
    state.mapPayload = null;
    renderPoiList();
    renderQueryLogs();
    renderConflicts();
    renderCoverage();
    renderMatchLogs();
    updateMapSource(EMPTY_COLLECTION);
  });

  els.poiDetailForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const poiId = els.poiIdInput.value.trim();
    if (poiId) {
      void loadPoiDetail(poiId);
    }
  });

  els.poiListRefresh.addEventListener("click", () => {
    state.poiListOffset = 0;
    void loadPoiList();
  });

  [
    els.poiSearch,
    els.filterCategory,
    els.filterReviewState,
    els.filterSource,
    els.filterTheme,
    els.filterThemeMatch,
    els.filterDiagnostics,
    els.filterOverrides,
    els.filterActiveOnly,
  ].forEach((element) => {
    element.addEventListener("change", () => {
      state.poiListOffset = 0;
      void loadPoiList();
    });
  });

  els.poiSearch.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      state.poiListOffset = 0;
      void loadPoiList();
    }
  });

  els.poiListPrev.addEventListener("click", () => {
    state.poiListOffset = Math.max(0, state.poiListOffset - PAGE_SIZE);
    void loadPoiList();
  });

  els.poiListNext.addEventListener("click", () => {
    if (state.poiListOffset + PAGE_SIZE < state.poiListTotal) {
      state.poiListOffset += PAGE_SIZE;
      void loadPoiList();
    }
  });

  els.poiListBody.addEventListener("click", (event) => {
    const row = event.target.closest("[data-poi-row-id]");
    if (row) {
      void loadPoiDetail(row.dataset.poiRowId);
    }
  });

  els.mapRefresh.addEventListener("click", () => {
    void loadMapPois();
  });

  [
    els.mapFilterCategory,
    els.mapFilterSearch,
    els.mapFilterReviewState,
    els.mapFilterSource,
    els.mapFilterTheme,
    els.mapFilterThemeMatch,
    els.mapFilterDiagnostics,
    els.mapFilterOverrides,
    els.mapFilterActiveOnly,
  ].forEach((element) => {
    element.addEventListener("change", () => {
      void loadMapPois();
    });
  });

  els.mapFilterSearch.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      void loadMapPois();
    }
  });

  els.queryLogRefresh.addEventListener("click", () => {
    state.queryLogOffset = 0;
    void loadQueryLogs();
  });

  els.queryLogFilters.addEventListener("submit", (event) => {
    event.preventDefault();
    state.queryLogOffset = 0;
    void loadQueryLogs();
  });

  els.queryLogPrev.addEventListener("click", () => {
    state.queryLogOffset = Math.max(0, state.queryLogOffset - LOG_PAGE_SIZE);
    void loadQueryLogs();
  });

  els.queryLogNext.addEventListener("click", () => {
    if (state.queryLogOffset + LOG_PAGE_SIZE < state.queryLogTotal) {
      state.queryLogOffset += LOG_PAGE_SIZE;
      void loadQueryLogs();
    }
  });

  els.queryLogBody.addEventListener("click", (event) => {
    const logButton = event.target.closest("[data-log-id]");
    if (logButton) {
      state.expandedLogId = state.expandedLogId === logButton.dataset.logId ? null : logButton.dataset.logId;
      renderQueryLogs();
      return;
    }
    const poiLink = event.target.closest("[data-poi-id]");
    if (poiLink) {
      void openPoiFromLink(poiLink.dataset.poiId);
    }
  });

  els.conflictsRefresh.addEventListener("click", () => {
    void loadConflicts();
  });

  els.conflictsFilters.addEventListener("submit", (event) => {
    event.preventDefault();
    void loadConflicts();
  });

  els.conflictsBody.addEventListener("click", (event) => {
    const poiLink = event.target.closest("[data-poi-id]");
    if (poiLink) {
      void openPoiFromLink(poiLink.dataset.poiId);
    }
  });

  els.coverageRefresh.addEventListener("click", () => {
    void loadCoverage();
  });

  els.matchLogRefresh.addEventListener("click", () => {
    void loadMatchLogs();
  });

  els.matchLogFilters.addEventListener("submit", (event) => {
    event.preventDefault();
    void loadMatchLogs();
  });

  els.matchLogBody.addEventListener("click", (event) => {
    const poiLink = event.target.closest("[data-poi-id]");
    if (poiLink) {
      void openPoiFromLink(poiLink.dataset.poiId);
    }
  });

  els.statusRefresh.addEventListener("click", () => {
    void loadStatus();
  });
}

async function boot() {
  await Promise.all([loadStatus(), loadCategories()]);
  if (hasAdminKey()) {
    void loadPoiList();
    void loadQueryLogs();
    void loadMapPois();
    void loadConflicts();
    void loadCoverage();
    void loadMatchLogs();
  }
}

function showView(view) {
  state.view = view;
  els.navButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  Object.entries(els.views).forEach(([name, element]) => {
    element.classList.toggle("is-active", name === view);
  });

  if (view === "map-browser") {
    initMapBrowser();
    setTimeout(() => state.mapBrowser?.resize(), 0);
    if (hasAdminKey()) {
      void loadMapPois();
    }
  }
  if (view === "conflicts" && hasAdminKey()) {
    void loadConflicts();
  }
  if (view === "coverage" && hasAdminKey()) {
    void loadCoverage();
  }
  if (view === "match-logs" && hasAdminKey()) {
    void loadMatchLogs();
  }
}

function updateKeyStatus() {
  setKeyMessage(hasAdminKey() ? "Admin key saved." : "No admin key saved.");
}

function setKeyMessage(message) {
  els.keyStatus.textContent = message;
}

function hasAdminKey() {
  return Boolean(localStorage.getItem(ADMIN_KEY_STORAGE));
}

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.admin) {
    const adminKey = localStorage.getItem(ADMIN_KEY_STORAGE);
    if (!adminKey) {
      throw new Error("Admin key is required for this request.");
    }
    headers.set("X-POI-Curator-Admin-Key", adminKey);
  }

  const url = new URL(path, window.location.origin);
  if (options.params) {
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value) !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url, { method: "GET", headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(readApiError(payload) || `${response.status} ${response.statusText}`);
  }
  return payload;
}

async function loadStatus() {
  const [healthResult, configResult] = await Promise.allSettled([
    requestJson("/v1/health"),
    requestJson("/v1/config"),
  ]);

  if (healthResult.status === "fulfilled") {
    state.health = healthResult.value;
  } else {
    state.health = { status: "error", scoring_source: "unknown", error: healthResult.reason.message };
  }

  if (configResult.status === "fulfilled") {
    state.config = configResult.value;
  } else {
    state.config = { error: configResult.reason.message };
  }

  renderHealthBadge();
  els.healthRaw.textContent = stringify(state.health);
  els.configRaw.textContent = stringify(state.config);
}

async function loadCategories() {
  try {
    state.categories = await requestJson("/v1/categories");
  } catch (error) {
    state.categories = [
      { slug: "history", label: "History" },
      { slug: "culture", label: "Culture" },
      { slug: "art", label: "Art" },
      { slug: "scenic", label: "Scenic" },
      { slug: "food", label: "Food" },
      { slug: "civic", label: "Civic / Infrastructure" },
      { slug: "mixed", label: "Mixed" },
    ];
  }
  populateCategorySelect(els.filterCategory);
  populateCategorySelect(els.mapFilterCategory);
}

function populateCategorySelect(select) {
  select.innerHTML = "";
  select.appendChild(new Option("Any", ""));
  state.categories.forEach((category) => {
    select.appendChild(new Option(category.label || category.slug, category.slug));
  });
}

function renderHealthBadge() {
  const source = state.health?.scoring_source || "unknown";
  els.healthBadge.textContent = source;
  els.healthBadge.className = `health-badge ${source}`;
}

async function loadPoiList() {
  if (!hasAdminKey()) {
    els.poiListStatus.textContent = "Enter an admin key, then refresh.";
    renderPoiList();
    return;
  }
  els.poiListStatus.textContent = "Loading POIs...";
  try {
    const payload = await requestJson("/v1/admin/pois", {
      admin: true,
      params: poiListParams(),
    });
    state.poiList = payload.items || [];
    state.poiListTotal = payload.total || 0;
    state.poiListOffset = payload.offset || 0;
    els.poiListStatus.textContent = "";
    renderPoiList();
  } catch (error) {
    state.poiList = [];
    state.poiListTotal = 0;
    els.poiListStatus.textContent = error.message;
    renderPoiList();
  }
}

function poiListParams() {
  const reviewState = els.filterReviewState.value;
  return {
    search: els.poiSearch.value.trim(),
    category: els.filterCategory.value,
    review_state: reviewState,
    source: els.filterSource.value.trim(),
    theme: els.filterTheme.value,
    theme_match: els.filterThemeMatch.value,
    has_diagnostics: els.filterDiagnostics.value,
    has_editorial_overrides: els.filterOverrides.value,
    active_only:
      reviewState === "gnis_demoted_pending_review" ? "false" : els.filterActiveOnly.value,
    limit: PAGE_SIZE,
    offset: state.poiListOffset,
  };
}

function renderPoiList() {
  els.poiListBody.innerHTML = "";
  if (!state.poiList.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.className = "empty-cell";
    cell.textContent = hasAdminKey() ? "No POIs match the current filters." : "Enter an admin key.";
    row.appendChild(cell);
    els.poiListBody.appendChild(row);
  }

  state.poiList.forEach((poi) => {
    const row = document.createElement("tr");
    row.className = "is-clickable";
    row.dataset.poiRowId = poi.poi_id;
    row.append(
      tableCell(poi.poi_id),
      tableCell(poi.name),
      tableCell(poi.primary_category),
      tableCell(poi.review_state),
      tableCell(poi.source),
      tableCell((poi.themes || []).join(", ")),
      tableCell(formatDate(poi.last_updated))
    );
    els.poiListBody.appendChild(row);
  });

  const start = state.poiListTotal ? state.poiListOffset + 1 : 0;
  const end = Math.min(state.poiListOffset + PAGE_SIZE, state.poiListTotal);
  els.poiListPage.textContent = `${start}-${end} of ${state.poiListTotal}`;
  els.poiListPrev.disabled = state.poiListOffset <= 0;
  els.poiListNext.disabled = state.poiListOffset + PAGE_SIZE >= state.poiListTotal;
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value ?? "";
  return cell;
}

async function loadPoiDetail(poiId) {
  showView("poi-detail");
  els.poiIdInput.value = poiId;
  destroyDetailMap();
  els.poiDetailContent.innerHTML = '<div class="empty-state">Loading POI detail...</div>';
  try {
    state.selectedPoi = await requestJson(`/v1/admin/pois/${encodeURIComponent(poiId)}`, {
      admin: true,
    });
    renderPoiDetail(state.selectedPoi, els.poiDetailContent, { includeMap: true });
  } catch (error) {
    els.poiDetailContent.innerHTML = "";
    els.poiDetailContent.appendChild(emptyState(`Could not load POI detail: ${error.message}`));
  }
}

async function openPoiFromLink(poiId) {
  if (!poiId) {
    return;
  }
  await loadPoiDetail(poiId);
}

function renderPoiDetail(poi, container, options = {}) {
  container.innerHTML = "";
  const canonical = poi.canonical || poi;
  const adminDetail = poi.canonical ? poi : null;

  const left = document.createElement("div");
  left.className = "detail-column";
  const right = document.createElement("div");
  right.className = "detail-column";

  left.appendChild(renderCanonicalFields(canonical, adminDetail?.editorial_overrides || {}));
  left.appendChild(renderFieldProvenance(canonical.provenance?.field_sources || {}));
  left.appendChild(renderEvidence(adminDetail?.evidence || canonical.evidence || []));
  left.appendChild(renderThemes(adminDetail?.themes || canonical.themes || []));

  right.appendChild(renderExternalLinks(poi));
  right.appendChild(renderAliases(adminDetail?.aliases || []));
  right.appendChild(renderDiagnostics(adminDetail?.match_diagnostics || []));
  if (options.includeMap) {
    right.appendChild(renderDetailMapCard(canonical));
  }

  if (options.compact) {
    container.className = "side-detail detail-column";
    container.append(...left.childNodes, ...right.childNodes);
  } else {
    container.className = "detail-grid";
    container.append(left, right);
  }

  if (options.includeMap) {
    initDetailMap(canonical.coordinates);
  }
}

function renderFieldProvenance(fieldSources) {
  const card = detailCard("Field Provenance");
  const fields = Object.entries(fieldSources || {});
  if (!fields.length) {
    card.appendChild(emptyState("No field-level provenance is recorded for this POI."));
    return card;
  }
  fields.forEach(([field, sources]) => {
    const row = document.createElement("div");
    row.className = "provenance-row";
    const name = document.createElement("span");
    name.className = "field-name-inline";
    name.textContent = field;
    const badges = document.createElement("span");
    badges.className = "link-row";
    (sources || []).forEach((source) => {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = source;
      badges.appendChild(badge);
    });
    row.append(name, badges);
    card.appendChild(row);
  });
  return card;
}

function renderCanonicalFields(poi, overrides = {}) {
  const card = detailCard("Canonical Fields");
  const table = document.createElement("div");
  table.className = "field-table";
  const fields = [
    ["poi_id", poi.poi_id],
    ["name", poi.name],
    ["primary_category", poi.primary_category],
    ["secondary_categories", poi.secondary_categories],
    ["coordinates", poi.coordinates],
    ["short_description", poi.short_description],
    ["why_it_matters", poi.why_it_matters],
    ["badges", poi.badges],
    ["extended_place", poi.extended_place],
    ["provenance", poi.provenance],
  ];
  fields.forEach(([name, value]) => {
    const nameCell = document.createElement("div");
    nameCell.className = "field-name";
    nameCell.textContent = name;
    const valueCell = document.createElement("div");
    valueCell.className = "field-value";
    valueCell.appendChild(renderValue(value));
    const override = overrides[name] || getOverrideInfo(poi, name);
    if (override) {
      const badge = document.createElement("span");
      badge.className = "edited-badge";
      badge.title = `Original source value: ${formatCompact(
        override.source_value ?? override.original
      )}`;
      badge.textContent = "edited";
      valueCell.appendChild(badge);
    }
    table.append(nameCell, valueCell);
  });
  card.appendChild(table);
  if (!Object.keys(overrides).length && !hasOverrideMetadata(poi)) {
    const note = document.createElement("p");
    note.className = "empty-state";
    note.style.marginTop = "10px";
    note.textContent =
      "No editorial overrides are recorded for the exposed canonical fields.";
    card.appendChild(note);
  }
  return card;
}

function renderEvidence(evidence) {
  const card = detailCard("Evidence");
  if (!evidence.length) {
    card.appendChild(emptyState("No evidence rows are exposed for this POI."));
    return card;
  }

  const groups = new Map();
  evidence.forEach((item) => {
    const source = item.source_name || item.source || item.source_id || item.source_type || "Unknown";
    if (!groups.has(source)) {
      groups.set(source, []);
    }
    groups.get(source).push(item);
  });

  groups.forEach((items, source) => {
    const group = document.createElement("section");
    group.className = "evidence-group";
    const heading = document.createElement("h3");
    heading.textContent = `${source} (${items.length})`;
    group.appendChild(heading);
    items.forEach((item) => {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = [
        item.evidence_type,
        item.label,
        item.external_record_id,
        item.confidence !== undefined ? `confidence ${item.confidence}` : null,
      ]
        .filter(Boolean)
        .join(" - ");
      const pre = document.createElement("pre");
      pre.textContent = stringify(item);
      details.append(summary, pre);
      group.appendChild(details);
    });
    card.appendChild(group);
  });

  return card;
}

function renderThemes(themes) {
  const card = detailCard("Theme Memberships");
  if (!themes.length) {
    card.appendChild(emptyState("No theme memberships are exposed for this POI."));
    return card;
  }

  themes.forEach((theme) => {
    const item = document.createElement("section");
    item.className = "theme-item";
    const heading = document.createElement("h3");
    heading.textContent = `${theme.label || theme.theme_slug} - ${theme.status}`;
    const meta = document.createElement("p");
    meta.className = "empty-state";
    meta.textContent = [
      `confidence ${formatNumber(theme.confidence)}`,
      theme.assignment_basis,
      theme.editorial_decision ? `editorial ${theme.editorial_decision}` : null,
      theme.is_query_active ? "query active" : "not query active",
    ]
      .filter(Boolean)
      .join(" | ");
    item.append(heading, meta);
    if (theme.rationale_summary) {
      const rationale = document.createElement("p");
      rationale.textContent = theme.rationale_summary;
      rationale.style.marginTop = "8px";
      item.appendChild(rationale);
    }
    if (theme.evidence?.length) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = `${theme.evidence.length} supporting evidence reference(s)`;
      const pre = document.createElement("pre");
      pre.textContent = stringify(theme.evidence);
      details.append(summary, pre);
      item.appendChild(details);
    }
    card.appendChild(item);
  });

  return card;
}

function renderExternalLinks(poi) {
  const card = detailCard("External Links");
  const row = document.createElement("div");
  row.className = "link-row";
  const links = buildExternalLinks(poi);
  if (!links.length) {
    card.appendChild(emptyState("No OSM or Wikidata ids are exposed for this POI."));
    return card;
  }
  links.forEach((link) => {
    const anchor = document.createElement("a");
    anchor.className = "external-link";
    anchor.href = link.href;
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
    anchor.textContent = link.label;
    row.appendChild(anchor);
  });
  card.appendChild(row);
  return card;
}

function renderAliases(aliases) {
  const card = detailCard("Aliases");
  if (!aliases.length) {
    card.appendChild(emptyState("No aliases recorded."));
    return card;
  }
  aliases.forEach((alias) => {
    const item = document.createElement("div");
    item.className = "evidence-group";
    item.textContent = [
      alias.alias_name,
      alias.alias_type,
      alias.source,
      alias.is_preferred ? "preferred" : null,
    ]
      .filter(Boolean)
      .join(" - ");
    card.appendChild(item);
  });
  return card;
}

function renderDiagnostics(diagnostics) {
  const card = detailCard("Match Diagnostics");
  if (!diagnostics.length) {
    card.appendChild(emptyState("No match diagnostics recorded."));
    return card;
  }
  diagnostics.forEach((diagnostic) => {
    const item = document.createElement("section");
    item.className = "diagnostic-item";
    const heading = document.createElement("h3");
    heading.textContent = `${diagnostic.source_id} - ${diagnostic.state}`;
    const body = document.createElement("p");
    body.textContent = [
      diagnostic.external_name,
      diagnostic.best_candidate_name,
      diagnostic.reviewer_notes,
      diagnostic.why_not_auto_linked,
    ]
      .filter(Boolean)
      .join(" | ");
    item.append(heading, body);
    card.appendChild(item);
  });
  return card;
}

function renderDetailMapCard(poi) {
  const card = detailCard("Location");
  if (!Array.isArray(poi.coordinates) || poi.coordinates.length < 2) {
    card.appendChild(emptyState("No coordinates available."));
    return card;
  }
  const map = document.createElement("div");
  map.id = "detail-map";
  map.className = "mini-map";
  card.appendChild(map);
  return card;
}

function initDetailMap(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length < 2 || !window.maplibregl) {
    return;
  }
  destroyDetailMap();
  state.detailMap = new maplibregl.Map({
    container: "detail-map",
    style: baseMapStyle(),
    center: coordinates,
    zoom: 15,
  });
  state.detailMap.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  state.detailMarker = new maplibregl.Marker().setLngLat(coordinates).addTo(state.detailMap);
}

function destroyDetailMap() {
  if (!state.detailMap) {
    return;
  }
  state.detailMap.remove();
  state.detailMap = null;
  state.detailMarker = null;
}

function initMapBrowser() {
  if (state.mapBrowser || !window.maplibregl) {
    return;
  }
  state.mapBrowser = new maplibregl.Map({
    container: "map-browser-map",
    style: baseMapStyle(),
    center: SANTA_FE_CENTER,
    zoom: DEFAULT_ZOOM,
  });
  state.mapBrowser.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  state.mapBrowser.on("load", () => {
    state.mapBrowser.addSource("pois", {
      type: "geojson",
      data: EMPTY_COLLECTION,
      cluster: true,
      clusterRadius: 42,
    });
    state.mapBrowser.addLayer({
      id: "poi-clusters",
      type: "circle",
      source: "pois",
      filter: ["has", "point_count"],
      paint: {
        "circle-color": "#2458c7",
        "circle-radius": ["step", ["get", "point_count"], 16, 20, 22, 75, 28],
        "circle-opacity": 0.88,
      },
    });
    state.mapBrowser.addLayer({
      id: "poi-cluster-count",
      type: "symbol",
      source: "pois",
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count_abbreviated"],
        "text-size": 12,
      },
      paint: { "text-color": "#ffffff" },
    });
    state.mapBrowser.addLayer({
      id: "poi-points",
      type: "circle",
      source: "pois",
      filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-radius": 7,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
        "circle-color": [
          "match",
          ["get", "review_state"],
          "reviewed",
          "#167a3a",
          "needs_review",
          "#a06000",
          "suppressed",
          "#b42318",
          "#2458c7",
        ],
      },
    });
    state.mapBrowser.on("click", "poi-points", (event) => {
      const poiId = event.features?.[0]?.properties?.poi_id;
      if (poiId) {
        void loadMapPoiDetail(poiId);
      }
    });
    state.mapBrowser.on("click", "poi-clusters", (event) => {
      const feature = event.features?.[0];
      const clusterId = feature?.properties?.cluster_id;
      const source = state.mapBrowser.getSource("pois");
      if (clusterId === undefined || !source?.getClusterExpansionZoom) {
        return;
      }
      source.getClusterExpansionZoom(clusterId, (error, zoom) => {
        if (error) {
          return;
        }
        state.mapBrowser.easeTo({
          center: feature.geometry.coordinates,
          zoom,
        });
      });
    });
    state.mapBrowser.on("mouseenter", "poi-points", () => {
      state.mapBrowser.getCanvas().style.cursor = "pointer";
    });
    state.mapBrowser.on("mouseleave", "poi-points", () => {
      state.mapBrowser.getCanvas().style.cursor = "";
    });
    updateMapSource(state.mapPayload?.feature_collection || EMPTY_COLLECTION);
  });
}

async function loadMapPois() {
  if (!hasAdminKey()) {
    els.mapStatus.textContent = "Enter an admin key, then refresh.";
    updateMapSource(EMPTY_COLLECTION);
    return;
  }
  els.mapStatus.textContent = "Loading map POIs...";
  try {
    const payload = await requestJson("/v1/admin/pois/map", {
      admin: true,
      params: mapParams(),
    });
    state.mapPayload = payload;
    updateMapSource(payload.feature_collection || EMPTY_COLLECTION);
    renderMapStatus(payload);
  } catch (error) {
    state.mapPayload = null;
    updateMapSource(EMPTY_COLLECTION);
    els.mapStatus.textContent = error.message;
  }
}

function mapParams() {
  const reviewState = els.mapFilterReviewState.value;
  return {
    search: els.mapFilterSearch.value.trim(),
    category: els.mapFilterCategory.value,
    review_state: reviewState,
    source: els.mapFilterSource.value.trim(),
    theme: els.mapFilterTheme.value,
    theme_match: els.mapFilterThemeMatch.value,
    has_diagnostics: els.mapFilterDiagnostics.value,
    has_editorial_overrides: els.mapFilterOverrides.value,
    active_only:
      reviewState === "gnis_demoted_pending_review" ? "false" : els.mapFilterActiveOnly.value,
    limit: 2000,
  };
}

function updateMapSource(featureCollection) {
  const source = state.mapBrowser?.getSource("pois");
  if (source?.setData) {
    source.setData(featureCollection);
  }
}

function renderMapStatus(payload) {
  if (!payload) {
    els.mapStatus.textContent = "";
    return;
  }
  if (payload.truncated) {
    els.mapStatus.textContent = `Showing ${payload.returned} of ${payload.total_matching} - apply filters or bbox to see more.`;
    return;
  }
  els.mapStatus.textContent = `Showing ${payload.returned} of ${payload.total_matching}.`;
}

async function loadMapPoiDetail(poiId) {
  els.mapDetailPanel.innerHTML = '<div class="empty-state">Loading POI detail...</div>';
  try {
    const detail = await requestJson(`/v1/admin/pois/${encodeURIComponent(poiId)}`, {
      admin: true,
    });
    renderPoiDetail(detail, els.mapDetailPanel, { includeMap: false, compact: true });
  } catch (error) {
    els.mapDetailPanel.innerHTML = "";
    els.mapDetailPanel.appendChild(emptyState(`Could not load POI detail: ${error.message}`));
  }
}

async function loadQueryLogs() {
  els.queryLogStatus.textContent = "Loading query logs...";
  try {
    const payload = await requestJson("/v1/admin/query-logs", {
      admin: true,
      params: queryLogParams(),
    });
    state.queryLogs = payload.items || [];
    state.queryLogTotal = payload.total || 0;
    state.queryLogOffset = payload.offset || 0;
    els.queryLogStatus.textContent = "";
    renderQueryLogs();
  } catch (error) {
    els.queryLogStatus.textContent = error.message;
    state.queryLogs = [];
    state.queryLogTotal = 0;
    renderQueryLogs();
  }
}

function queryLogParams() {
  return {
    endpoint: document.getElementById("log-endpoint").value.trim(),
    start: localDateTimeToIso(document.getElementById("log-start").value),
    end: localDateTimeToIso(document.getElementById("log-end").value),
    min_result_count: document.getElementById("log-min-results").value,
    max_result_count: document.getElementById("log-max-results").value,
    limit: LOG_PAGE_SIZE,
    offset: state.queryLogOffset,
  };
}

function renderQueryLogs() {
  els.queryLogBody.innerHTML = "";
  if (!state.queryLogs.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.className = "empty-cell";
    cell.textContent = hasAdminKey() ? "No query logs found." : "Enter an admin key, then refresh.";
    row.appendChild(cell);
    els.queryLogBody.appendChild(row);
  }

  state.queryLogs.forEach((log) => {
    const row = document.createElement("tr");
    row.className = "is-clickable";
    row.append(
      logCell(log.endpoint, log.id),
      logCell(formatDate(log.timestamp), log.id),
      logCell(log.result_count, log.id),
      logCell(log.data_source, log.id),
      logCell(log.duration_ms, log.id)
    );
    els.queryLogBody.appendChild(row);

    if (state.expandedLogId === String(log.id)) {
      const detailRow = document.createElement("tr");
      const detailCell = document.createElement("td");
      detailCell.colSpan = 5;
      detailCell.appendChild(renderQueryLogDetail(log));
      detailRow.appendChild(detailCell);
      els.queryLogBody.appendChild(detailRow);
    }
  });

  const start = state.queryLogTotal ? state.queryLogOffset + 1 : 0;
  const end = Math.min(state.queryLogOffset + LOG_PAGE_SIZE, state.queryLogTotal);
  els.queryLogPage.textContent = `${start}-${end} of ${state.queryLogTotal}`;
  els.queryLogPrev.disabled = state.queryLogOffset <= 0;
  els.queryLogNext.disabled = state.queryLogOffset + LOG_PAGE_SIZE >= state.queryLogTotal;
}

async function loadConflicts() {
  if (!hasAdminKey()) {
    els.conflictsStatus.textContent = "Enter an admin key, then refresh.";
    renderConflicts();
    return;
  }
  els.conflictsStatus.textContent = "Loading conflicts...";
  try {
    const payload = await requestJson("/v1/admin/conflicts", {
      admin: true,
      params: {
        source_pair: document.getElementById("conflict-source-pair").value.trim(),
        field_name: document.getElementById("conflict-field").value,
        limit: 100,
        offset: 0,
      },
    });
    state.conflicts = payload.items || [];
    els.conflictsStatus.textContent = `${payload.total || 0} conflict(s)`;
    renderConflicts();
  } catch (error) {
    state.conflicts = [];
    els.conflictsStatus.textContent = error.message;
    renderConflicts();
  }
}

function renderConflicts() {
  els.conflictsBody.innerHTML = "";
  if (!state.conflicts.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.className = "empty-cell";
    cell.textContent = hasAdminKey() ? "No conflicts match the filters." : "Enter an admin key.";
    row.appendChild(cell);
    els.conflictsBody.appendChild(row);
    return;
  }
  state.conflicts.forEach((conflict) => {
    const row = document.createElement("tr");
    row.append(
      poiButtonCell(conflict.name, conflict.poi_id),
      tableCell(conflict.field_name),
      tableCell((conflict.sources || []).join(", ")),
      tableCell(formatCompact(conflict.canonical_value)),
      tableCell(formatDate(conflict.last_observed_at))
    );
    els.conflictsBody.appendChild(row);
  });
}

async function loadCoverage() {
  if (!hasAdminKey()) {
    els.coverageStatus.textContent = "Enter an admin key, then refresh.";
    renderCoverage();
    return;
  }
  els.coverageStatus.textContent = "Loading coverage...";
  try {
    state.coverage = await requestJson("/v1/admin/coverage", { admin: true });
    els.coverageStatus.textContent = `total_pois=${state.coverage.total_pois || 0}`;
    renderCoverage();
  } catch (error) {
    state.coverage = null;
    els.coverageStatus.textContent = error.message;
    renderCoverage();
  }
}

function renderCoverage() {
  els.coverageContent.innerHTML = "";
  if (!state.coverage) {
    els.coverageContent.appendChild(emptyState("No coverage payload loaded."));
    return;
  }
  [
    ["By Source", state.coverage.by_source],
    ["By Source Pair", state.coverage.by_source_pair],
    ["Single Source Gaps", state.coverage.single_source_gaps],
  ].forEach(([title, values]) => {
    const card = detailCard(title);
    const table = document.createElement("div");
    table.className = "field-table";
    Object.entries(values || {}).forEach(([key, value]) => {
      const name = document.createElement("div");
      name.className = "field-name";
      name.textContent = key;
      const count = document.createElement("div");
      count.className = "field-value";
      count.textContent = value;
      table.append(name, count);
    });
    card.appendChild(table);
    els.coverageContent.appendChild(card);
  });
}

async function loadMatchLogs() {
  if (!hasAdminKey()) {
    els.matchLogStatus.textContent = "Enter an admin key, then refresh.";
    renderMatchLogs();
    return;
  }
  els.matchLogStatus.textContent = "Loading match logs...";
  try {
    const payload = await requestJson("/v1/admin/match-logs", {
      admin: true,
      params: {
        source: document.getElementById("match-log-source").value.trim(),
        decision: document.getElementById("match-log-decision").value,
        start: localDateTimeToIso(document.getElementById("match-log-start").value),
        end: localDateTimeToIso(document.getElementById("match-log-end").value),
        limit: 100,
        offset: 0,
      },
    });
    state.matchLogs = payload.items || [];
    els.matchLogStatus.textContent = `${payload.total || 0} log(s)`;
    renderMatchLogs();
  } catch (error) {
    state.matchLogs = [];
    els.matchLogStatus.textContent = error.message;
    renderMatchLogs();
  }
}

function renderMatchLogs() {
  els.matchLogBody.innerHTML = "";
  if (!state.matchLogs.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "empty-cell";
    cell.textContent = hasAdminKey() ? "No match logs found." : "Enter an admin key.";
    row.appendChild(cell);
    els.matchLogBody.appendChild(row);
    return;
  }
  state.matchLogs.forEach((log) => {
    const row = document.createElement("tr");
    row.append(
      tableCell(log.candidate_source),
      tableCell(log.candidate_external_id),
      tableCell(log.decision),
      tableCell(log.match_strategy),
      poiButtonCell(log.canonical_name || log.canonical_poi_id || "", log.canonical_poi_id),
      tableCell(formatDate(log.decided_at))
    );
    els.matchLogBody.appendChild(row);
  });
}

function poiButtonCell(label, poiId) {
  const cell = document.createElement("td");
  if (!poiId) {
    cell.textContent = label || "";
    return cell;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-button";
  button.dataset.poiId = poiId;
  button.textContent = label || poiId;
  cell.appendChild(button);
  return cell;
}

function logCell(value, logId) {
  const cell = document.createElement("td");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-button";
  button.dataset.logId = logId;
  button.textContent = value ?? "";
  cell.appendChild(button);
  return cell;
}

function renderQueryLogDetail(log) {
  const detail = document.createElement("div");
  detail.className = "query-log-detail";

  const results = document.createElement("div");
  results.className = "link-row";
  (log.results || []).forEach((result) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button";
    button.dataset.poiId = result.poi_id;
    button.textContent = `${result.rank}. ${result.poi_id}`;
    results.appendChild(button);
  });
  if (!log.results?.length) {
    results.appendChild(emptyState("No result POI ids in this log."));
  }

  const requestDetails = document.createElement("details");
  requestDetails.open = true;
  const requestSummary = document.createElement("summary");
  requestSummary.textContent = "request_payload";
  const requestPre = document.createElement("pre");
  requestPre.textContent = stringify(log.request_payload);
  requestDetails.append(requestSummary, requestPre);

  const resultDetails = document.createElement("details");
  const resultSummary = document.createElement("summary");
  resultSummary.textContent = "results";
  const resultPre = document.createElement("pre");
  resultPre.textContent = stringify(log.results || []);
  resultDetails.append(resultSummary, resultPre);

  detail.append(results, requestDetails, resultDetails);
  return detail;
}

function detailCard(title) {
  const card = document.createElement("section");
  card.className = "detail-card";
  const heading = document.createElement("h2");
  heading.textContent = title;
  card.appendChild(heading);
  return card;
}

function emptyState(message) {
  const div = document.createElement("div");
  div.className = "empty-state";
  div.textContent = message;
  return div;
}

function renderValue(value) {
  if (value === null || value === undefined || value === "") {
    return emptyState("None");
  }
  if (Array.isArray(value)) {
    const span = document.createElement("span");
    span.textContent = value.map((item) => formatCompact(item)).join(", ");
    return span;
  }
  if (typeof value === "object") {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "View JSON";
    const pre = document.createElement("pre");
    pre.textContent = stringify(value);
    details.append(summary, pre);
    return details;
  }
  const span = document.createElement("span");
  span.textContent = String(value);
  return span;
}

function buildExternalLinks(poi) {
  const links = [];
  if (poi.external_links?.wikidata) {
    links.push({ label: "Open in Wikidata", href: poi.external_links.wikidata });
  }
  if (poi.external_links?.osm) {
    links.push({ label: "Open in OSM", href: poi.external_links.osm });
  }
  if (links.length) {
    return links;
  }
  const wikidataId = findWikidataId(poi);
  if (wikidataId) {
    links.push({ label: "Open in Wikidata", href: `https://www.wikidata.org/wiki/${wikidataId}` });
  }
  const osm = findOsmReference(poi);
  if (osm?.url) {
    links.push({ label: "Open in OSM", href: osm.url });
  } else if (osm?.id && osm?.type) {
    links.push({ label: "Open in OSM", href: `https://www.openstreetmap.org/${osm.type}/${osm.id}` });
  }
  return links;
}

function findWikidataId(value) {
  const direct = findFirstMatchingValue(value, (key, item) => {
    return key.toLowerCase().includes("wikidata") && typeof item === "string" && /^Q\d+$/.test(item);
  });
  if (direct) {
    return direct;
  }
  return findFirstMatchingValue(value, (_key, item) => typeof item === "string" && /^Q\d+$/.test(item));
}

function findOsmReference(value) {
  const url = findFirstMatchingValue(value, (_key, item) => {
    return typeof item === "string" && item.includes("openstreetmap.org/");
  });
  if (url) {
    return { url };
  }
  const id = findFirstMatchingValue(value, (key, item) => {
    return /osm.*id|openstreetmap.*id/i.test(key) && (typeof item === "string" || typeof item === "number");
  });
  const typeValue = findFirstMatchingValue(value, (key, item) => {
    return /osm.*type|openstreetmap.*type/i.test(key) && typeof item === "string";
  });
  const type = normalizeOsmType(typeValue);
  return id ? { id, type } : null;
}

function findFirstMatchingValue(value, predicate) {
  const seen = new Set();
  function visit(item, key = "") {
    if (!item || seen.has(item)) {
      return null;
    }
    if (typeof item === "object") {
      seen.add(item);
      if (Array.isArray(item)) {
        for (const child of item) {
          const found = visit(child, key);
          if (found) return found;
        }
        return null;
      }
      for (const [childKey, childValue] of Object.entries(item)) {
        if (predicate(childKey, childValue)) {
          return childValue;
        }
        const found = visit(childValue, childKey);
        if (found) return found;
      }
      return null;
    }
    return predicate(key, item) ? item : null;
  }
  return visit(value);
}

function normalizeOsmType(value) {
  if (!value) {
    return null;
  }
  const normalized = String(value).toLowerCase();
  if (["node", "way", "relation"].includes(normalized)) {
    return normalized;
  }
  if (normalized === "n") return "node";
  if (normalized === "w") return "way";
  if (normalized === "r") return "relation";
  return null;
}

function getOverrideInfo(poi, fieldName) {
  const overrides = poi?.provenance?.editorial_overrides || poi?.provenance?.overrides;
  if (!overrides || typeof overrides !== "object") {
    return null;
  }
  return overrides[fieldName] || null;
}

function hasOverrideMetadata(poi) {
  return Boolean(poi?.provenance?.editorial_overrides || poi?.provenance?.overrides);
}

function baseMapStyle() {
  return {
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
    layers: [{ id: "carto", type: "raster", source: "carto" }],
  };
}

function readApiError(payload) {
  if (!payload) return "";
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || stringify(item)).join("; ");
  return payload.message || stringify(payload);
}

function localDateTimeToIso(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

function stringify(value) {
  return JSON.stringify(value, null, 2);
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatNumber(value) {
  return typeof value === "number" ? value.toFixed(2) : value;
}

function formatCompact(value) {
  if (value === null || value === undefined) return "None";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
