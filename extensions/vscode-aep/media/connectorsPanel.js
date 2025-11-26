// connectorsPanel.js
// Connections hub UI for NAVI webview (VS Code)

(function () {
    /** @type {any} */
    // Use the vscode API that was already acquired in the HTML
    const vscode = window.vscode;

    // ---- 1. Connector metadata ---------------------------------------------

    const CONNECTOR_CATEGORIES = [
        { id: "all", label: "All" },
        { id: "pm", label: "Project Management" },
        { id: "chat", label: "Chat & Collaboration" },
        { id: "code", label: "Code & Repos" },
        { id: "ci", label: "CI / DevOps" },
        { id: "meetings", label: "Meetings" },
    ];

    /** @type {Array<{
     *  id: string;
     *  name: string;
     *  description: string;
     *  category: string;
     *  authType: 'apiKey' | 'oauth';
     *  icon: string;
     * }>} */
    const CONNECTORS = [
        {
            id: "jira",
            name: "Jira",
            description: "Sync issues, epics, and sprints for task-aware assistance.",
            category: "pm",
            authType: "apiKey",
            icon: "jira.svg",
        },
        {
            id: "slack",
            name: "Slack",
            description: "Pull channel history, threads, and decisions from chat.",
            category: "chat",
            authType: "oauth",
            icon: "slack.svg",
        },
        {
            id: "teams",
            name: "Microsoft Teams",
            description: "Sync Teams channels and conversations.",
            category: "chat",
            authType: "oauth",
            icon: "teams.svg",
        },
        {
            id: "zoom",
            name: "Zoom",
            description: "Ingest meeting transcripts and summaries.",
            category: "meetings",
            authType: "oauth",
            icon: "zoom.svg",
        },
        {
            id: "github",
            name: "GitHub",
            description: "Index PRs, code reviews, and repository history.",
            category: "code",
            authType: "oauth",
            icon: "github.svg",
        },
        {
            id: "jenkins",
            name: "Jenkins / CI",
            description: "Track builds, pipelines, and deployment history.",
            category: "ci",
            authType: "apiKey",
            icon: "jenkins.svg",
        },
        {
            id: "generic_http",
            name: "Generic HTTP",
            description: "Connect any REST service as a custom data source.",
            category: "code",
            authType: "apiKey",
            icon: "http.svg",
        },
    ];

    // ---- 2. State ----------------------------------------------------------

    const state = {
        isOpen: false,
        search: "",
        activeCategory: "all",
        // statusMap: { [connectorId]: { status, message, lastSyncedAt } }
        statusMap: /** @type {Record<string, {status: string, message?: string, lastSyncedAt?: string} | undefined>} */ (
            {}
        ),
        // Which connector is currently showing its inline form
        expandedFormFor: /** @type {string | null} */ (null),
        isBusyFor: /** @type {Record<string, boolean>} */ ({}),
        baseUrl: (typeof window !== 'undefined' && window.AEP_CONFIG && window.AEP_CONFIG.backendBaseUrl) || "http://127.0.0.1:8787",
    };

    // ---- 3. DOM helpers ----------------------------------------------------

    function $(selector) {
        return /** @type {HTMLElement | null} */ (document.querySelector(selector));
    }

    function createEl(tag, className, children) {
        const el = document.createElement(tag);
        if (className) el.className = className;
        if (Array.isArray(children)) {
            for (const c of children) {
                if (typeof c === "string") {
                    el.appendChild(document.createTextNode(c));
                } else if (c instanceof Node) {
                    el.appendChild(c);
                }
            }
        }
        return el;
    }

    // ---- 4. Backend helpers (via extension host to avoid CSP) -------------

    function requestConnectorStatus() {
        if (vscode) {
            vscode.postMessage({ type: 'connectors.getStatus' });
        }
    }

    function refreshAllStatuses() {
        // Request status via extension host (avoids CSP issues)
        requestConnectorStatus();
    }

    // Listen for messages from the extension host
    window.addEventListener("message", (event) => {
        const msg = event.data;
        switch (msg.type) {
            case 'connectors.hide': {
                console.log('[ConnectorsPanel] Received hide message from extension');
                closeConnectionsModal();
                break;
            }
            case 'connectors.jiraSyncResult': {
                console.log('[ConnectorsPanel] Jira sync result:', msg);
                if (msg.ok) {
                    console.log(`[ConnectorsPanel] Sync successful: ${msg.synced_issues} issues`);
                } else {
                    console.error('[ConnectorsPanel] Sync failed:', msg.error);
                }
                // Re-render to update UI state
                renderConnectorList();
                break;
            }
            case 'connectors.status': {
                // msg.data = { connectors: [ { provider, status, last_sync_ts, ... }, ... ] }
                const connectors = msg.data?.connectors || [];
                // Don't completely overwrite statusMap - preserve successful connections
                for (const c of connectors) {
                    // Only update if we don't have a successful connection already
                    const currentStatus = state.statusMap[c.provider];
                    if (!currentStatus || currentStatus.status !== 'connected') {
                        state.statusMap[c.provider] = {
                            status: c.status || "disconnected",
                            message: c.message || "",
                            lastSyncedAt: c.last_sync_ts || c.last_index_ts,
                        };
                    }
                }
                renderConnectorList();
                break;
            }
            case 'connectors.statusError': {
                console.error('[NAVI] Connector status error:', msg.error);
                // Show error in UI
                break;
            }
            case 'connectors.jiraConnect.result': {
                // Handle new result message format
                const { ok, provider, status, error } = msg;
                state.isBusyFor[provider] = false;

                if (ok) {
                    // Update status map
                    state.statusMap[provider] = {
                        status: status || 'connected',
                        message: '',
                        lastSyncedAt: new Date().toISOString(),
                    };
                    vscode.postMessage({
                        type: 'showToast',
                        message: 'Connected to Jira! Initial sync started.',
                        level: 'info'
                    });
                    // Don't auto-refresh status to avoid overriding successful connection
                    // User can manually refresh if needed
                } else {
                    // Update status map to show error
                    state.statusMap[provider] = {
                        status: 'error',
                        message: error || 'Connection failed',
                        lastSyncedAt: undefined,
                    };
                    vscode.postMessage({
                        type: 'showToast',
                        message: `Jira connection failed: ${error || 'Unknown error'}`,
                        level: 'error'
                    });
                }
                renderConnectorList();
                break;
            }
            // Legacy message handlers for backward compatibility
            case 'connectors.jiraConnected': {
                state.isBusyFor['jira'] = false;
                vscode.postMessage({
                    type: 'showToast',
                    message: 'Connected to Jira! Initial sync started.',
                    level: 'info'
                });
                setTimeout(() => requestConnectorStatus(), 3000);
                break;
            }
            case 'connectors.jiraConnectError': {
                state.isBusyFor['jira'] = false;
                vscode.postMessage({
                    type: 'showToast',
                    message: `Jira connection failed: ${msg.error || 'Unknown error'}`,
                    level: 'error'
                });
                renderConnectorList();
                break;
            }
        }
    });

    // ---- 5. Connect flows --------------------------------------------------

    async function handleApiKeyConnect(id) {
        console.log('[ConnectorsPanel] handleApiKeyConnect called for:', id);
        const row = document.querySelector(`.aep-connector-row[data-id="${id}"]`);
        if (!row) {
            console.error('[ConnectorsPanel] Row not found for:', id);
            return;
        }

        const urlInput = /** @type {HTMLInputElement | null} */ (
            row.querySelector("input[data-field='base_url']")
        );
        const emailInput = /** @type {HTMLInputElement | null} */ (
            row.querySelector("input[data-field='email']")
        );
        const tokenInput = /** @type {HTMLInputElement | null} */ (
            row.querySelector("input[data-field='api_token']")
        );

        const base_url = urlInput ? urlInput.value.trim() : "";
        const email = emailInput ? emailInput.value.trim() : "";
        const api_token = tokenInput ? tokenInput.value.trim() : "";

        console.log('[ConnectorsPanel] Form values:', { base_url, email, api_token: api_token ? '***' : '' });

        if (!base_url || !api_token) {
            vscode.postMessage({
                type: 'showToast',
                message: 'Please provide at least Base URL and API token.',
                level: 'warning'
            });
            return;
        }

        state.isBusyFor[id] = true;
        renderConnectorList();

        // Send connect request via extension host (Jira only for now)
        if (id === 'jira' && vscode) {
            console.log('[ConnectorsPanel] Sending connectors.jiraConnect message');
            vscode.postMessage({
                type: 'connectors.jiraConnect',
                baseUrl: base_url,
                email: email || undefined,
                apiToken: api_token,
            });
        } else {
            // Fallback or other connectors (not implemented yet)
            state.isBusyFor[id] = false;
            vscode.postMessage({
                type: 'showToast',
                message: `Connect flow for ${id} not implemented yet`,
                level: 'info'
            });
            renderConnectorList();
        }
    }

    async function handleOAuthConnect(id) {
        // OAuth flow - open external URL via extension host
        try {
            if (vscode) {
                vscode.postMessage({
                    type: "openExternal",
                    url: `https://api.slack.com/apps`, // Placeholder
                });
            }
            // Refresh status after delay
            setTimeout(() => requestConnectorStatus(), 4000);
        } catch (err) {
            console.error("[NAVI] OAuth start error", id, err);
            state.statusMap[id] = {
                status: "error",
                message: String(err),
            };
        }
    }

    // ---- 6. Rendering ------------------------------------------------------

    function getFilteredConnectors() {
        const q = state.search.toLowerCase();
        const cat = state.activeCategory;

        return CONNECTORS.filter((c) => {
            const matchesCat = cat === "all" || c.category === cat;
            const matchesSearch =
                !q ||
                c.name.toLowerCase().includes(q) ||
                c.description.toLowerCase().includes(q);
            return matchesCat && matchesSearch;
        });
    }

    function renderStatusPill(connector) {
        const status = state.statusMap[connector.id]?.status || "disconnected";

        // Only show pill for connected or error status
        if (status === "disconnected") {
            return null;
        }

        const el = createEl("span", `aep-status-pill aep-status-${status}`, []);
        const dot = createEl("span", "status-dot", []);
        const text = status === "connected" ? "Connected" : "Error";
        el.appendChild(dot);
        el.appendChild(document.createTextNode(text));
        return el;
    }

    function renderConnectorRow(connector) {
        const row = createEl("div", "aep-connector-row", []);
        row.dataset.id = connector.id;
        row.dataset.category = connector.category;

        const header = createEl("div", "aep-connector-header", []);

        // Left side: icon + text
        const left = createEl("div", "aep-connector-left", []);

        // Icon
        const iconContainer = createEl("div", "connector-icon", []);
        const icon = document.createElement("img");
        const iconsUri = (window.AEP_CONFIG && window.AEP_CONFIG.iconsUri) || './icons';
        icon.src = `${iconsUri}/${connector.icon}`;
        icon.alt = connector.name;
        icon.width = 32;
        icon.height = 32;
        iconContainer.appendChild(icon);

        // Text container
        const textContainer = createEl("div", "connector-text", []);
        const name = createEl("div", "aep-connector-title", [connector.name]);
        const desc = createEl("div", "aep-connector-desc", [connector.description]);
        textContainer.appendChild(name);
        textContainer.appendChild(desc);

        left.appendChild(iconContainer);
        left.appendChild(textContainer);

        // Right side: status pill + button
        const right = createEl("div", "aep-connector-right", []);

        const statusPill = renderStatusPill(connector);
        if (statusPill) {
            right.appendChild(statusPill);
        }

        const status = state.statusMap[connector.id]?.status || "disconnected";

        // For Jira when connected, add an "Update & Test" button first
        if (connector.id === "jira" && status === "connected") {
            const syncBtn = createEl(
                "button",
                "aep-btn aep-btn-secondary aep-connector-sync",
                ["Update & Test"]
            );
            syncBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                console.log('[ConnectorsPanel] Jira sync button clicked');
                if (vscode) {
                    vscode.postMessage({ type: 'connectors.jiraSyncNow' });
                }
            });

            if (state.isBusyFor[connector.id]) {
                syncBtn.disabled = true;
                syncBtn.textContent = "Syncing…";
            }

            right.appendChild(syncBtn);
        }

        const btnLabel = status === "connected" ? "Manage" :
            status === "error" ? "Retry" : "Connect";

        const btn = createEl(
            "button",
            "aep-btn aep-btn-primary aep-connector-action",
            [btnLabel]
        );
        btn.addEventListener("click", () => {
            state.expandedFormFor =
                state.expandedFormFor === connector.id ? null : connector.id;
            renderConnectorList();
        });

        if (state.isBusyFor[connector.id]) {
            btn.disabled = true;
            btn.textContent = "Connecting…";
        }

        right.appendChild(btn);

        header.appendChild(left);
        header.appendChild(right);
        row.appendChild(header);

        // Inline form section
        if (state.expandedFormFor === connector.id) {
            const formWrapper = createEl("div", "aep-connector-form", []);

            if (connector.authType === "apiKey") {
                const urlInput = createEl("input", "aep-input", []);
                urlInput.placeholder = "Base URL (e.g., https://your-domain.atlassian.net)";
                urlInput.dataset.field = "base_url";

                const emailInput = createEl("input", "aep-input", []);
                emailInput.placeholder = "Email (optional)";
                emailInput.dataset.field = "email";

                const tokenInput = createEl("input", "aep-input", []);
                tokenInput.placeholder = "API token / PAT";
                tokenInput.type = "password";
                tokenInput.dataset.field = "api_token";

                const formActions = createEl("div", "aep-form-actions", []);
                const connectBtn = createEl("button", "aep-btn aep-btn-primary", [
                    state.statusMap[connector.id]?.status === "connected"
                        ? "Update & Test"
                        : "Connect",
                ]);
                connectBtn.addEventListener("click", () =>
                    handleApiKeyConnect(connector.id)
                );

                formActions.appendChild(connectBtn);
                formWrapper.appendChild(urlInput);
                formWrapper.appendChild(emailInput);
                formWrapper.appendChild(tokenInput);
                formWrapper.appendChild(formActions);
            } else if (connector.authType === "oauth") {
                const info = createEl("p", "aep-oauth-info", [
                    `You'll be redirected to ${connector.name} to authorize NAVI. We only store the minimal tokens required to read data; NAVI never posts on your behalf without permission.`,
                ]);

                const btnRow = createEl("div", "aep-form-actions", []);
                const connectBtn = createEl("button", "aep-btn aep-btn-primary", [
                    state.statusMap[connector.id]?.status === "connected"
                        ? "Re-connect"
                        : "Connect via browser",
                ]);
                connectBtn.addEventListener("click", () =>
                    handleOAuthConnect(connector.id)
                );
                btnRow.appendChild(connectBtn);

                formWrapper.appendChild(info);
                formWrapper.appendChild(btnRow);
            }

            row.appendChild(formWrapper);
        }

        return row;
    }

    function renderConnectorList() {
        const container = $("#aep-connectors-list");
        if (!container) return;
        container.innerHTML = "";

        const connectors = getFilteredConnectors();
        if (!connectors.length) {
            container.appendChild(
                createEl("div", "aep-empty", [
                    "No connectors match your search. Try a different keyword or category.",
                ])
            );
            return;
        }

        for (const c of connectors) {
            container.appendChild(renderConnectorRow(c));
        }
    }

    function renderFilters() {
        console.log('[ConnectorsPanel] Rendering filters');
        const filterRow = $("#aep-connectors-filters");
        if (!filterRow) {
            console.error('[ConnectorsPanel] Filter container not found!');
            return;
        }
        filterRow.innerHTML = "";

        for (const cat of CONNECTOR_CATEGORIES) {
            const btn = createEl(
                "button",
                `aep-chip ${state.activeCategory === cat.id ? "aep-chip-active" : ""}`,
                [cat.label]
            );
            btn.addEventListener("click", () => {
                console.log('[ConnectorsPanel] Filter clicked:', cat.id);
                state.activeCategory = cat.id;
                renderConnectorList();
                renderFilters();
            });
            filterRow.appendChild(btn);
        }
        console.log('[ConnectorsPanel] Rendered', CONNECTOR_CATEGORIES.length, 'filter chips');
    }

    // ---- 7. Modal open/close ----------------------------------------------

    function openConnectionsModal() {
        const modal = $("#aep-connections-modal");
        const backdrop = $("#aep-connections-backdrop");
        if (!modal || !backdrop) return;

        state.isOpen = true;
        modal.classList.add("aep-modal-open");
        backdrop.classList.add("aep-backdrop-open");
        refreshAllStatuses();
    }

    function closeConnectionsModal() {
        console.log('[ConnectorsPanel] Closing modal');

        // Check if running in a separate webview panel (ConnectorsPanel class)
        const modal = $("#aep-connections-modal");
        const backdrop = $("#aep-connections-backdrop");

        if (!modal || !backdrop) {
            // We're in a standalone panel (ConnectorsPanel), send close message
            console.log('[ConnectorsPanel] In standalone panel, sending closePanel message');
            if (vscode) {
                vscode.postMessage({ type: 'closePanel' });
            }
            return;
        }

        // Regular modal close (NaviWebviewProvider)
        console.log('[ConnectorsPanel] In modal mode, closing modal');
        state.isOpen = false;
        modal.classList.remove("aep-modal-open");
        backdrop.classList.remove("aep-backdrop-open");

        // Also notify extension that connectors was closed
        if (vscode) {
            vscode.postMessage({ type: 'connectors.close' });
        }
    }

    function initConnectionsUI() {
        console.log('[ConnectorsPanel] Initializing UI');

        // Debug: Log all elements with close-related IDs
        const allElements = document.querySelectorAll('[id*="close"], [id*="panel"]');
        console.log('[ConnectorsPanel] Found elements with close/panel IDs:', Array.from(allElements).map(el => ({ id: el.id, tag: el.tagName })));

        // Close button - enhanced detection with multiple fallbacks
        let closePanelBtn = $("#aep-connections-close") || $("#aep-close-panel") || document.querySelector('[title="Close"]') || document.querySelector('button:contains("✕")');
        console.log('[ConnectorsPanel] Close button element found:', !!closePanelBtn, closePanelBtn ? closePanelBtn.id : 'none');

        if (closePanelBtn) {
            console.log('[ConnectorsPanel] Adding click listener to close button');
            closePanelBtn.addEventListener("click", (event) => {
                console.log('[ConnectorsPanel] Close button clicked!', event);
                event.preventDefault();
                event.stopPropagation();
                closeConnectionsModal();
            });
            console.log('[ConnectorsPanel] Click listener added successfully');
        } else {
            console.warn('[ConnectorsPanel] Close button not found - will retry after DOM update');
            // Retry after a short delay in case DOM hasn't fully loaded
            setTimeout(() => {
                closePanelBtn = $("#aep-connections-close") || $("#aep-close-panel") || document.querySelector('[title="Close"]');
                if (closePanelBtn) {
                    console.log('[ConnectorsPanel] Close button found on retry');
                    closePanelBtn.addEventListener("click", (event) => {
                        console.log('[ConnectorsPanel] Close button clicked (retry)!', event);
                        event.preventDefault();
                        event.stopPropagation();
                        closeConnectionsModal();
                    });
                }
            }, 100);
        }        // Backdrop click to close
        const backdrop = $("#aep-connections-backdrop");
        if (backdrop) {
            backdrop.addEventListener("click", () => {
                console.log('[ConnectorsPanel] Backdrop clicked');
                closeConnectionsModal();
            });
        }

        // Escape key to close
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && state.isOpen) {
                console.log('[ConnectorsPanel] Escape key pressed');
                closeConnectionsModal();
            }
        });

        // Search input
        const searchInput = /** @type {HTMLInputElement | null} */ (
            $("#aep-connectors-search")
        );
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                state.search = searchInput.value;
                renderConnectorList();
            });
        }

        renderFilters();
        renderConnectorList();
        console.log('[ConnectorsPanel] UI initialization complete');
    }

    // Expose to other scripts (panel.js)
    window.AEPConnections = {
        open: openConnectionsModal,
        close: closeConnectionsModal,
        init: initConnectionsUI,
    };

    // Auto-init when DOM ready - for ConnectorsPanel, it's always visible
    window.addEventListener("DOMContentLoaded", () => {
        console.log('[ConnectorsPanel] DOMContentLoaded - initializing');
        const container = $("#aep-connectors-container");
        if (container) {
            console.log('[ConnectorsPanel] Container found, initializing UI');
            initConnectionsUI();
            // Request initial status
            requestConnectorStatus();
        } else {
            console.error('[ConnectorsPanel] Container not found!');
        }
    });
})();
