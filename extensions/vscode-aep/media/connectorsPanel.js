// extensions/vscode-aep/media/connectorsPanel.js

/* global acquireVsCodeApi */

(function () {
  // -------------------------------------------------------------------------
  // VS Code API – safe single acquisition
  // -------------------------------------------------------------------------
  const w = /** @type {any} */ (window);
  const vscode = w.__aepVscode || acquireVsCodeApi();
  w.__aepVscode = vscode;

  const CONNECTORS = [
    {
      id: "jira",
      name: "Jira",
      vendor: "Atlassian",
      category: "work_tracking",
      tags: ["Work tracking"],
      description: "Issues, epics, and sprints for engineering teams.",
      status: "not_connected",
      icon: "jira.svg",
    },
    {
      id: "github_issues",
      name: "GitHub Issues",
      vendor: "GitHub",
      category: "work_tracking",
      tags: ["Work tracking", "Code & repos"],
      description: "Track work items directly from your repos.",
      status: "coming_soon",
      icon: "github.svg",
    },
    {
      id: "github",
      name: "GitHub",
      vendor: "GitHub",
      category: "code",
      tags: ["Code & repos", "CI / Pipelines"],
      description: "Code, PRs, reviews, and CI checks.",
      status: "not_connected",
      icon: "github.svg",
    },
    {
      id: "gitlab",
      name: "GitLab",
      vendor: "GitLab",
      category: "code",
      tags: ["Code & repos", "CI / Pipelines"],
      description: "Source code, issues, and pipelines.",
      status: "coming_soon",
      icon: "gitlab.svg",
    },
    {
      id: "slack",
      name: "Slack",
      vendor: "Slack",
      category: "chat",
      tags: ["Chat", "Docs / Knowledge"],
      description: "Channels, threads, and DMs for your org.",
      status: "not_connected",
      icon: "slack.svg",
    },
    {
      id: "teams",
      name: "Microsoft Teams",
      vendor: "Microsoft",
      category: "chat",
      tags: ["Chat", "Meetings"],
      description: "Teams chats, channels, and meetings.",
      status: "not_connected",
      icon: "teams.svg",
    },
    {
      id: "meet",
      name: "Google Meet",
      vendor: "Google",
      category: "meetings",
      tags: ["Meetings"],
      description: "Meet calls, recordings, and transcripts.",
      status: "not_connected",
      icon: "http.svg",
    },
    {
      id: "zoom",
      name: "Zoom",
      vendor: "Zoom",
      category: "meetings",
      tags: ["Meetings"],
      description: "Meetings, recordings, and transcripts.",
      status: "not_connected",
      icon: "zoom.svg",
    },
    {
      id: "confluence",
      name: "Confluence",
      vendor: "Atlassian",
      category: "docs",
      tags: ["Docs / Knowledge"],
      description: "Design docs, specs, and architecture pages.",
      status: "not_connected",
      icon: "confluence.svg",
    },
    {
      id: "jenkins",
      name: "Jenkins",
      vendor: "Jenkins",
      category: "ci",
      tags: ["CI / Pipelines"],
      description: "Builds, pipelines, and deployment status.",
      status: "coming_soon",
      icon: "jenkins.svg",
    },
  ];

  const FILTERS = [
    { id: "all", label: "All" },
    { id: "work_tracking", label: "Work tracking" },
    { id: "code", label: "Code & repos" },
    { id: "chat", label: "Chat" },
    { id: "meetings", label: "Meetings" },
    { id: "ci", label: "CI / Pipelines" },
    { id: "storage", label: "Storage" },
    { id: "docs", label: "Docs / Knowledge" },
    { id: "other", label: "Other" },
  ];

  const state = {
    search: "",
    filter: "all",
    statuses: {}, // { jira: "connected" | "disconnected" | "error" }
    offline: false,
  };

  function qs(sel) {
    return document.querySelector(sel);
  }

  function createRoot() {
    const root = document.getElementById("root");
    root.innerHTML = `
      <div class="aep-connectors-header">
        <div>
          <h2 class="aep-connectors-title">Connections</h2>
          <p class="aep-connectors-subtitle">
            Connect Jira, Slack, Teams, Zoom, GitHub, and more so NAVI can use full organizational context.
          </p>
        </div>
      </div>
      <div class="aep-connectors-controls">
        <div class="aep-connectors-search-wrap">
          <span class="aep-connectors-search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search connectors..."
            class="aep-connectors-search"
            id="connectors-search"
          />
        </div>
        <div class="aep-connectors-filters" id="connectors-filters"></div>
      </div>
      <div class="aep-connectors-status aep-connectors-status--error" id="connectors-offline" style="display: none;">
        Connectors backend is offline. Using static marketplace list for now.
      </div>
      <div class="aep-connectors-list" id="connectors-list"></div>
    `;

    // Filters
    const filterRow = qs("#connectors-filters");
    FILTERS.forEach((f) => {
      const btn = document.createElement("button");
      btn.className = "aep-connectors-filter-chip";
      btn.dataset.filterId = f.id;
      btn.textContent = f.label;
      if (f.id === state.filter) btn.classList.add("aep-connectors-filter-chip--active");
      btn.addEventListener("click", () => {
        state.filter = f.id;
        updateFilters();
        renderList();
      });
      filterRow.appendChild(btn);
    });

    const searchInput = qs("#connectors-search");
    searchInput.addEventListener("input", (e) => {
      state.search = e.target.value.toLowerCase();
      renderList();
    });
  }

  function updateFilters() {
    document
      .querySelectorAll('.aep-connectors-filter-chip[data-filter-id]')
      .forEach((el) => {
        const id = el.getAttribute("data-filter-id");
        if (id === state.filter) {
          el.classList.add("aep-connectors-filter-chip--active");
        } else {
          el.classList.remove("aep-connectors-filter-chip--active");
        }
      });
  }

  function statusFor(id) {
    return state.statuses[id] || "disconnected";
  }

  function renderList() {
    const list = qs("#connectors-list");
    if (!list) return;

    list.innerHTML = "";

    const offlineBanner = qs("#connectors-offline");
    offlineBanner.style.display = state.offline ? "block" : "none";

    let items = [...CONNECTORS];

    // Map backend statuses (jira, slack, github, …)
    items = items.map((c) => {
      const backendStatus = state.statuses[c.id] || state.statuses[c.id.replace("_issues", "")];
      let mapped = c.status;
      if (backendStatus === "connected") {
        mapped = "connected";
      } else if (backendStatus === "error") {
        mapped = "error";
      } else if (backendStatus === "disconnected") {
        if (c.status === "coming_soon") {
          mapped = "coming_soon";
        } else {
          mapped = "not_connected";
        }
      }
      return { ...c, status: mapped };
    });

    // Filter
    items = items.filter((c) => {
      if (state.filter === "all") return true;
      if (state.filter === "work_tracking") return c.category === "work_tracking";
      if (state.filter === "code") return c.category === "code";
      if (state.filter === "chat") return c.category === "chat";
      if (state.filter === "meetings") return c.category === "meetings";
      if (state.filter === "ci") return c.category === "ci";
      if (state.filter === "docs") return c.category === "docs";
      if (state.filter === "storage") return c.category === "storage";
      if (state.filter === "other") return c.category === "other";
      return true;
    });

    // Search
    if (state.search) {
      items = items.filter((c) => {
        const hay = `${c.name} ${c.vendor} ${c.description}`.toLowerCase();
        return hay.includes(state.search);
      });
    }

    const iconBase = window.AEP_CONNECTOR_ICON_BASE || "media/icons";

    items.forEach((c) => {
      const row = document.createElement("div");
      row.className = "aep-connectors-card";

      const iconUrl = c.icon && iconBase ? `${iconBase}/${c.icon}` : "";
      console.log(`[AEP] Icon for ${c.name}: ${iconUrl || 'fallback to letter'}`);

      // Create main container
      const main = document.createElement("div");
      main.className = "aep-connectors-card-main";

      // Create icon circle
      const iconCircle = document.createElement("div");
      iconCircle.className = "aep-connectors-icon-circle";

      if (iconUrl) {
        const img = document.createElement("img");
        img.src = iconUrl;
        img.alt = c.name || "";
        iconCircle.appendChild(img);
      } else {
        iconCircle.textContent = (c.name || "").charAt(0).toUpperCase();
      }

      // Create text container
      const textContainer = document.createElement("div");
      textContainer.className = "aep-connectors-card-text";

      // Create title row
      const titleRow = document.createElement("div");
      titleRow.className = "aep-connectors-card-title-row";

      const title = document.createElement("div");
      title.className = "aep-connectors-card-title";
      title.textContent = c.name || "";

      titleRow.appendChild(title);
      titleRow.insertAdjacentHTML('beforeend', renderStatusBadge(c));

      // Create description
      const desc = document.createElement("div");
      desc.className = "aep-connectors-card-desc";
      desc.textContent = c.description || "";

      // Create meta
      const meta = document.createElement("div");
      meta.className = "aep-connectors-card-meta";
      meta.textContent = c.vendor || "";

      textContainer.appendChild(titleRow);
      textContainer.appendChild(desc);
      textContainer.appendChild(meta);

      main.appendChild(iconCircle);
      main.appendChild(textContainer);

      // Create side container
      const side = document.createElement("div");
      side.className = "aep-connectors-card-side";
      side.insertAdjacentHTML('beforeend', renderActionButton(c));

      row.appendChild(main);
      row.appendChild(side);

      const buttons = row.querySelectorAll("button[data-connector-id]");
      buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.getAttribute("data-connector-id");
          if (!id) return;
          if (c.status === "coming_soon") return;
          const action = btn.getAttribute("data-action") || "connect";
          vscode.postMessage({ type: "action", connectorId: id, action });
        });
      });

      list.appendChild(row);
    });
  }

  function renderStatusBadge(c) {
    switch (c.status) {
      case "connected":
        return `<span class="aep-connectors-pill aep-connectors-pill--connected">Connected</span>`;
      case "coming_soon":
        return `<span class="aep-connectors-pill aep-connectors-pill--soon">Coming soon</span>`;
      case "error":
        return `<span class="aep-connectors-pill aep-connectors-pill--error">Error</span>`;
      case "not_connected":
      default:
        return `<span class="aep-connectors-pill aep-connectors-pill--disconnected">Not connected</span>`;
    }
  }

  function renderActionButton(c) {
    if (c.status === "coming_soon") {
      return `<button class="aep-connectors-connect-btn" disabled>Preview</button>`;
    }

    if (c.status === "connected") {
      if (c.id === "slack") {
        return `
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="sync">Sync</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>
        `;
      }
      if (c.id === "github") {
        return `
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="index">Index Repo</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>
        `;
      }
      if (c.id === "confluence") {
        return `
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="sync">Sync</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="subscribe">Subscribe</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>
        `;
      }
      if (c.id === "teams") {
        return `
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="subscribe">Subscribe</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>
        `;
      }
      if (c.id === "zoom") {
        return `
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="sync">Sync</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>
        `;
      }
      if (c.id === "meet") {
        return `
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="subscribe">Subscribe</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="sync">Sync</button>
          <button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>
        `;
      }
      return `<button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Reconnect</button>`;
    }

    return `<button class="aep-connectors-connect-btn" data-connector-id="${c.id}" data-action="connect">Connect</button>`;
  }

  // -----------------------------------------------------------------------
  // Messages from extension host
  // -----------------------------------------------------------------------

  window.addEventListener("message", (event) => {
    const message = event.data;
    console.log("[AEP] Received message:", message.type, message.payload);
    switch (message.type) {
      case "status": {
        /** @type {ConnectorStatusPayload} */
        const payload = message.payload || {};
        console.log("[AEP] Processing status payload:", payload);
        const map = {};
        (payload.items || []).forEach((s) => {
          map[s.id] = s.status;
        });
        state.statuses = map;
        state.offline = !!payload.offline;
        console.log("[AEP] Updated state:", { offline: state.offline, statuses: state.statuses });
        renderList();
        break;
      }
      case "connectResult": {
        const { connectorId, ok, error } = message.payload || {};
        if (!ok && error) {
          showToast(`Failed to connect ${connectorId}: ${error}`);
        } else if (ok) {
          showToast(`Connected ${connectorId}`);
        }
        break;
      }
      case "syncResult": {
        const { connectorId, ok, error, details } = message.payload || {};
        if (!ok && error) {
          showToast(`Sync failed (${connectorId}): ${error}`);
        } else if (ok) {
          showToast(`Synced ${connectorId}${details ? `: ${details}` : ""}`);
        }
        break;
      }
      default:
        break;
    }
  });

  function showToast(text) {
    const root = document.body;
    const toast = document.createElement("div");
    toast.className = "aep-toast";
    toast.textContent = text;
    root.appendChild(toast);
    setTimeout(() => {
      toast.classList.add("aep-toast--visible");
    }, 10);
    setTimeout(() => {
      toast.classList.remove("aep-toast--visible");
      setTimeout(() => root.removeChild(toast), 200);
    }, 2500);
  }

  // Test function to verify webview can make HTTP requests
  async function testHTTP() {
    try {
      console.log("[AEP] Testing direct HTTP access...");
      const response = await fetch("http://127.0.0.1:8787/api/connectors/marketplace/status");
      console.log("[AEP] Direct HTTP test result:", response.status, response.statusText);
      if (response.ok) {
        const data = await response.json();
        console.log("[AEP] Direct HTTP success - offline:", data.offline, "items:", data.items?.length);
        return data;
      }
    } catch (error) {
      console.error("[AEP] Direct HTTP test failed:", error);
    }
    return null;
  }

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", async () => {
    console.log("[AEP] DOM loaded, initializing connectors panel");
    console.log("[AEP] Icon base available:", !!window.AEP_CONNECTOR_ICON_BASE);
    console.log("[AEP] Icon base value:", window.AEP_CONNECTOR_ICON_BASE);

    // Test direct HTTP access
    const directResult = await testHTTP();
    if (directResult && !directResult.offline) {
      console.log("[AEP] Direct HTTP works! Using direct backend access.");
      state.offline = false;
      const map = {};
      (directResult.items || []).forEach((s) => {
        map[s.id] = s.status;
      });
      state.statuses = map;
    }

    createRoot();
    renderList();
    console.log("[AEP] Requesting status from extension");
    vscode.postMessage({ type: "getStatus" });
  });
})();
