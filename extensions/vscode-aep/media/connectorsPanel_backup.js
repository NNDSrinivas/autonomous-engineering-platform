// connectorsMarketplace.js
// Web-based connectors marketplace for the NAVI webview

/**
 * ConnectorsMarketplace
 *
 * VS Code webview "Connections" marketplace for NAVI.
 *
 * Features:
 * - Static catalog of connectors (Jira, Slack, Teams, Zoom, GitHub, etc.)
 * - Search bar (by name & description)
 * - Category filter chips
 * - Shows status: Connected / Not connected / Coming soon
 * - Tries to fetch real status from backend, but falls back gracefully
 *
 * Expected HTML anchor in panel.html:
 *   <div id="aep-connectors-root" class="aep-connectors-root" hidden></div>
 *
 * The main panel script should instantiate this and wire it to the
 * "wand → Connections" button.
 */

/**
 * Static catalog – this is your "marketplace".
 * Later you can move this to backend / database,
 * but the panel UI does not need to change.
 */
const CONNECTOR_CATALOG = [
  // ---- Work tracking / planning ----
  {
    id: "jira",
    name: "Jira",
    description: "Issues, epics, and sprints for engineering teams.",
    category: "work-tracking",
    provider: "Atlassian",
    featured: true,
  },
  {
    id: "github_issues",
    name: "GitHub Issues",
    description: "Track work items directly from your repos.",
    category: "work-tracking",
    provider: "GitHub",
  },
  {
    id: "linear",
    name: "Linear",
    description: "Modern issue tracking for fast-moving teams.",
    category: "work-tracking",
    provider: "Linear",
    badge: "Soon",
  },
  {
    id: "asana",
    name: "Asana",
    description: "Tasks and projects across your org.",
    category: "work-tracking",
    provider: "Asana",
    badge: "Soon",
  },

  // ---- Code / repos / PRs ----
  {
    id: "github",
    name: "GitHub",
    description: "Code, PRs, reviews, and CI checks.",
    category: "code",
    provider: "GitHub",
    featured: true,
  },
  {
    id: "gitlab",
    name: "GitLab",
    description: "Source code, issues, and pipelines.",
    category: "code",
    provider: "GitLab",
    badge: "Soon",
  },
  {
    id: "bitbucket",
    name: "Bitbucket",
    description: "Code hosting and PR workflows.",
    category: "code",
    provider: "Atlassian",
    badge: "Soon",
  },

  // ---- Chat / collaboration ----
  {
    id: "slack",
    name: "Slack",
    description: "Channels, threads, and DMs as searchable memory.",
    category: "chat",
    provider: "Slack",
    featured: true,
  },
  {
    id: "msteams",
    name: "Microsoft Teams",
    description: "Teams chats and channels linked to work.",
    category: "chat",
    provider: "Microsoft",
    badge: "Soon",
  },
  {
    id: "discord",
    name: "Discord",
    description: "Community & internal dev server conversations.",
    category: "chat",
    provider: "Discord",
    badge: "Soon",
  },

  // ---- Meetings ----
  {
    id: "zoom",
    name: "Zoom",
    description: "Meeting transcripts and recordings.",
    category: "meetings",
    provider: "Zoom",
    featured: true,
  },
  {
    id: "google_meet",
    name: "Google Meet",
    description: "Calls and transcripts from Google Workspace.",
    category: "meetings",
    provider: "Google",
    badge: "Soon",
  },
  {
    id: "teams_meetings",
    name: "Teams Meetings",
    description: "Meeting recordings & transcripts.",
    category: "meetings",
    provider: "Microsoft",
    badge: "Soon",
  },

  // ---- CI / CD ----
  {
    id: "jenkins",
    name: "Jenkins",
    description: "Builds, jobs, and pipeline status.",
    category: "ci",
    provider: "Jenkins",
  },
  {
    id: "github_actions",
    name: "GitHub Actions",
    description: "CI workflows and deployment checks.",
    category: "ci",
    provider: "GitHub",
    featured: true,
  },
  {
    id: "circleci",
    name: "CircleCI",
    description: "Pipelines and build status.",
    category: "ci",
    provider: "CircleCI",
    badge: "Soon",
  },

  // ---- Storage / documents ----
  {
    id: "confluence",
    name: "Confluence",
    description: "Design docs and runbooks for every task.",
    category: "knowledge",
    provider: "Atlassian",
    featured: true,
  },
  {
    id: "notion",
    name: "Notion",
    description: "Project docs, specs, and personal notes.",
    category: "knowledge",
    provider: "Notion",
    badge: "Soon",
  },
  {
    id: "google_drive",
    name: "Google Drive",
    description: "Docs, sheets, and slides as context.",
    category: "storage",
    provider: "Google",
    badge: "Soon",
  },
  {
    id: "onedrive",
    name: "OneDrive",
    description: "Files from Microsoft 365.",
    category: "storage",
    provider: "Microsoft",
    badge: "Soon",
  },

  // ---- Other / misc ----
  {
    id: "gmail",
    name: "Gmail",
    description: "Important email threads linked to tasks.",
    category: "other",
    provider: "Google",
    badge: "Soon",
  },
  {
    id: "google_calendar",
    name: "Google Calendar",
    description: "Schedule awareness for meetings & deadlines.",
    category: "other",
    provider: "Google",
    badge: "Soon",
  },
];

const CATEGORY_FILTERS = [
  { id: "all", label: "All" },
  { id: "work-tracking", label: "Work tracking" },
  { id: "code", label: "Code & repos" },
  { id: "chat", label: "Chat" },
  { id: "meetings", label: "Meetings" },
  { id: "ci", label: "CI / Pipelines" },
  { id: "storage", label: "Storage" },
  { id: "knowledge", label: "Docs / Knowledge" },
  { id: "other", label: "Other" },
];

class ConnectorsMarketplace {
  constructor() {
    this.root = document.getElementById("aep-connectors-root");

    if (!this.root) {
      console.warn("[NAVI] ConnectorsMarketplace: #aep-connectors-root not found – panel disabled");
      return;
    }

    this.root.classList.add("aep-connectors-root");
    this.root.hidden = true;

    this.searchInput = null;
    this.filtersRow = null;
    this.listContainer = null;
    this.statusBanner = null;
    this.currentFilter = "all";
    this.searchQuery = "";
    this.isOpen = false;

    // Initial state from catalog (default = disconnected or coming_soon)
    this.connectors = CONNECTOR_CATALOG.map((c) => ({
      ...c,
      status: c.badge === "Soon" ? "coming_soon" : "disconnected",
    }));

    this.renderShell();
    this.attachEvents();
    this.refreshStatusFromBackend();
  }

  /** Public API used by panel.js */
  open() {
    if (!this.root) return;
    this.isOpen = true;
    this.root.hidden = false;
    this.root.classList.add("aep-connectors-root--visible");
    this.focusSearch();
  }

  close() {
    if (!this.root) return;
    this.isOpen = false;
    this.root.classList.remove("aep-connectors-root--visible");
    this.root.hidden = true;
  }

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  // ---------- Internal rendering ---------- //

  renderShell() {
    if (!this.root) return;

    this.root.innerHTML = `
      <div class="aep-connectors-modal">
        <div class="aep-connectors-header">
          <div class="aep-connectors-title-block">
            <h2 class="aep-connectors-title">Connections</h2>
            <p class="aep-connectors-subtitle">
              Connect Jira, Slack, Teams, Zoom, GitHub, and more so NAVI can use full organizational context.
            </p>
          </div>
          <button class="aep-connectors-close" aria-label="Close connectors panel">
            ×
          </button>
        </div>

        <div class="aep-connectors-controls">
          <div class="aep-connectors-search-wrap">
            <span class="aep-connectors-search-icon">🔍</span>
            <input
              id="aep-connectors-search"
              class="aep-connectors-search"
              type="search"
              placeholder="Search connectors..."
            />
          </div>
          <div class="aep-connectors-filters" id="aep-connectors-filters"></div>
        </div>

        <div class="aep-connectors-status" id="aep-connectors-status"></div>

        <div class="aep-connectors-list" id="aep-connectors-list">
          <!-- cards inserted here -->
        </div>
      </div>
    `;

    this.searchInput = this.root.querySelector("#aep-connectors-search");
    this.filtersRow = this.root.querySelector("#aep-connectors-filters");
    this.listContainer = this.root.querySelector("#aep-connectors-list");
    this.statusBanner = this.root.querySelector("#aep-connectors-status");

    this.renderFilters();
    this.renderList();
  }

  renderFilters() {
    if (!this.filtersRow) return;

    const chips = CATEGORY_FILTERS.map((f) => {
      const active = f.id === this.currentFilter;
      return `
        <button
          class="aep-connectors-filter-chip ${active ? "aep-connectors-filter-chip--active" : ""
        }"
          data-filter="${f.id}"
        >
          ${f.label}
        </button>
      `;
    }).join("");

    this.filtersRow.innerHTML = chips;
  }

  renderList() {
    if (!this.listContainer) return;

    const q = this.searchQuery.toLowerCase();
    const filtered = this.connectors.filter((c) => {
      const matchesCategory =
        this.currentFilter === "all" || c.category === this.currentFilter;
      const matchesQuery =
        !q ||
        c.name.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.provider.toLowerCase().includes(q);
      return matchesCategory && matchesQuery;
    });

    if (filtered.length === 0) {
      this.listContainer.innerHTML = `
        <div class="aep-connectors-empty">
          <p>No connectors match your search yet.</p>
          <p class="aep-connectors-empty-sub">
            Try a different keyword or category, or keep building NAVI – the marketplace will grow with you.
          </p>
        </div>
      `;
      return;
    }

    this.listContainer.innerHTML = filtered
      .map((c) => this.renderConnectorCard(c))
      .join("");
  }

  renderConnectorCard(c) {
    const statusLabel =
      c.status === "connected"
        ? "Connected"
        : c.status === "coming_soon"
          ? "Coming soon"
          : "Not connected";

    const statusClass =
      c.status === "connected"
        ? "aep-connectors-pill--connected"
        : c.status === "coming_soon"
          ? "aep-connectors-pill--soon"
          : "aep-connectors-pill--disconnected";

    const badge = c.badge
      ? `<span class="aep-connectors-badge">${c.badge}</span>`
      : "";

    const connectButtonLabel =
      c.status === "coming_soon"
        ? "Preview"
        : c.status === "connected"
          ? "Manage"
          : "Connect";

    const connectButtonDisabled = c.status === "coming_soon" ? "disabled" : "";

    return `
      <div class="aep-connectors-card" data-connector-id="${c.id}">
        <div class="aep-connectors-card-main">
          <div class="aep-connectors-icon-circle">
            ${c.name.slice(0, 2).toUpperCase()}
          </div>
          <div class="aep-connectors-card-text">
            <div class="aep-connectors-card-title-row">
              <h3 class="aep-connectors-card-title">${c.name}</h3>
              ${badge}
            </div>
            <p class="aep-connectors-card-desc">${c.description}</p>
            <p class="aep-connectors-card-meta">${c.provider}</p>
          </div>
        </div>
        <div class="aep-connectors-card-side">
          <span class="aep-connectors-pill ${statusClass}">
            ${statusLabel}
          </span>
          <button
            class="aep-connectors-connect-btn"
            data-connector-id="${c.id}"
            ${connectButtonDisabled}
          >
            ${connectButtonLabel}
          </button>
        </div>
      </div>
    `;
  }

  focusSearch() {
    if (this.searchInput) {
      setTimeout(() => this.searchInput?.focus(), 20);
    }
  }

  // ---------- Events ---------- //

  attachEvents() {
    if (!this.root) return;

    // Close button
    const closeBtn = this.root.querySelector(".aep-connectors-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => this.close());
    }

    // Escape key closes panel
    window.addEventListener("keydown", (evt) => {
      if (!this.isOpen) return;
      if (evt.key === "Escape") {
        this.close();
      }
    });

    // Search input
    if (this.searchInput) {
      this.searchInput.addEventListener("input", (e) => {
        this.searchQuery = e.target.value ?? "";
        this.renderList();
      });
    }

    // Delegate clicks for filter chips + connect buttons + backdrop
    this.root.addEventListener("click", (evt) => {
      const target = evt.target;
      if (!target) return;

      // Close on backdrop click (click outside modal)
      if (target === this.root) {
        this.close();
        return;
      }

      // Filter chip
      const filterChip = target.closest(".aep-connectors-filter-chip");
      if (filterChip && this.filtersRow?.contains(filterChip)) {
        const filterId = filterChip.dataset.filter;
        if (filterId && filterId !== this.currentFilter) {
          this.currentFilter = filterId;
          this.renderFilters();
          this.renderList();
        }
        return;
      }

      // Connect / Manage button
      const connectBtn = target.closest(".aep-connectors-connect-btn");
      if (connectBtn) {
        const id = connectBtn.dataset.connectorId;
        if (id) {
          this.onConnectClick(id);
        }
      }
    });
  }

  onConnectClick(id) {
    const connector = this.connectors.find((c) => c.id === id);
    if (!connector) return;

    if (connector.status === "coming_soon") {
      // For now, just show a friendly message in status banner
      this.setStatusBanner(
        `"${connector.name}" is marked as Coming soon. Backend wiring is not enabled yet.`,
        "info"
      );
      return;
    }

    // TODO: In the future this can open OAuth / device auth flows
    // For now, just explain that this is where the setup will live.
    this.setStatusBanner(
      `Connector "${connector.name}" will use NAVI's connector framework (OAuth / PAT / bot tokens). ` +
      `For now this is a placeholder – wire it to /api/connectors/${id}/connect when ready.`,
      "info"
    );
  }

  setStatusBanner(message, level = "info") {
    if (!this.statusBanner) return;
    if (!message) {
      this.statusBanner.textContent = "";
      this.statusBanner.className = "aep-connectors-status";
      return;
    }

    this.statusBanner.textContent = message;
    this.statusBanner.className =
      "aep-connectors-status " +
      (level === "error"
        ? "aep-connectors-status--error"
        : "aep-connectors-status--info");
  }

  // ---------- Backend status sync (optional) ---------- //

  /**
   * Try to fetch real connector status from backend.
   * If the call fails (no endpoint / server error), we silently fall back
   * to static defaults so the panel still works.
   */
  async refreshStatusFromBackend() {
    try {
      const baseUrl = window.AEP_BACKEND_BASE_URL;
      if (!baseUrl) {
        console.warn("[NAVI] ConnectorsMarketplace: AEP_BACKEND_BASE_URL not set – skipping status fetch");
        return;
      }

      const url = `${baseUrl.replace(/\/$/, "")}/api/connectors/marketplace/status`;
      const res = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        console.warn("[NAVI] ConnectorsMarketplace: status fetch failed with", res.status);
        this.setStatusBanner("Connectors backend is not ready yet. Showing placeholder list.", "info");
        return;
      }

      const body = await res.json();

      if (!body?.items || !Array.isArray(body.items)) {
        console.warn("[NAVI] ConnectorsMarketplace: unexpected status payload", body);
        return;
      }

      const map = new Map();
      for (const item of body.items) {
        if (!item || !item.id || !item.status) continue;
        map.set(item.id, item.status);
      }

      this.connectors = this.connectors.map((c) => {
        const status = map.get(c.id);
        return status ? { ...c, status } : c;
      });

      this.setStatusBanner("", "info");
      this.renderList();
    } catch (err) {
      console.warn("[NAVI] ConnectorsMarketplace: status fetch error", err);
      this.setStatusBanner(
        "Connectors backend is offline. Using static marketplace list for now.",
        "info"
      );
      // We keep showing the static list – no crash.
    }
  }
}

// Make it globally available
window.ConnectorsMarketplace = ConnectorsMarketplace;