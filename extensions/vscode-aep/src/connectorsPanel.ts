// extensions/vscode-aep/src/connectorsPanel.ts

import * as vscode from "vscode";

interface ConnectorStatus {
    id: string;
    name: string;
    category: string;
    status: "connected" | "disconnected" | "error";
    error?: string;
}

interface ConnectorStatusPayload {
    items: ConnectorStatus[];
    offline?: boolean;
}

export class ConnectorsPanel {
    public static currentPanel: ConnectorsPanel | undefined;

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private readonly _backendBaseUrl: string;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.ViewColumn.Beside;

        if (ConnectorsPanel.currentPanel) {
            ConnectorsPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            "aepConnectors",
            "Connections",
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            }
        );

        ConnectorsPanel.currentPanel = new ConnectorsPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        const config = vscode.workspace.getConfiguration("aep");
        const naviBackendUrl = config.get<string>("navi.backendUrl") || "http://127.0.0.1:8000";

        // Extract the root URL by stripping /api/navi/chat from the NAVI backend URL
        this._backendBaseUrl = naviBackendUrl.replace(/\/api\/navi\/chat\/?$/, "");
        console.log("[AEP] ConnectorsPanel initialized with backend URL:", this._backendBaseUrl);

        this._panel.iconPath = vscode.Uri.joinPath(
            this._extensionUri,
            "media",
            "icons",
            "aep-activitybar.png"
        );

        this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);
        this._setWebviewMessageListener(this._panel.webview);

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }

    private _getAuthToken(): string | undefined {
        const config = vscode.workspace.getConfiguration("aep");
        const configured = config.get<string>("navi.authToken");
        if (configured && configured.trim()) {
            return configured.trim();
        }
        const envToken =
            process.env.AEP_AUTH_TOKEN ||
            process.env.AEP_SESSION_TOKEN ||
            process.env.AEP_ACCESS_TOKEN;
        if (envToken && envToken.trim()) {
            return envToken.trim();
        }
        return undefined;
    }

    private _buildHeaders(extra?: Record<string, string>): Record<string, string> {
        const headers: Record<string, string> = { ...(extra || {}) };
        const authToken = this._getAuthToken();
        if (authToken) {
            headers["Authorization"] = authToken.startsWith("Bearer ")
                ? authToken
                : `Bearer ${authToken}`;
        }
        return headers;
    }

    public dispose() {
        ConnectorsPanel.currentPanel = undefined;

        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }

        this._panel.dispose();
    }

    // -----------------------------------------------------------------------
    // Webview wiring
    // -----------------------------------------------------------------------

    private _setWebviewMessageListener(webview: vscode.Webview) {
        webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case "getStatus":
                        await this._handleGetStatus();
                        return;
                    case "action":
                        await this._handleAction(message.action, message.connectorId);
                        return;
                    case "connect":
                        await this._handleConnect(message.connectorId);
                        return;
                    default:
                        return;
                }
            },
            undefined,
            this._disposables
        );
    }

    private async _handleGetStatus() {
        const url = `${this._backendBaseUrl}/api/connectors/marketplace/status`;
        console.log("[AEP] Fetching connector status from:", url);

        try {
            const res = await fetch(url, {
                method: "GET",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "User-Agent": "VSCode-AEP-Extension/1.0"
                }),
            });

            console.log("[AEP] Fetch response status:", res.status, res.statusText);

            if (!res.ok) {
                const errorText = await res.text();
                console.error("[AEP] Backend error response:", errorText);
                throw new Error(`HTTP ${res.status}: ${res.statusText} - ${errorText}`);
            }

            const data = (await res.json()) as ConnectorStatusPayload;
            console.log("[AEP] Backend response:", data);

            this._panel.webview.postMessage({
                type: "status",
                payload: { items: data.items, offline: !!data.offline },
            });
        } catch (err: any) {
            console.error("[AEP] Connector status error:", err?.message || err);
            console.error("[AEP] Backend URL was:", url);
            console.error("[AEP] Full error:", err);

            const offlinePayload: ConnectorStatusPayload = {
                items: [],
                offline: true,
            };

            this._panel.webview.postMessage({
                type: "status",
                payload: offlinePayload,
            });
        }
    }

    private async _handleConnect(connectorId: string) {
        switch (connectorId) {
            case "jira":
                await this._connectJira();
                break;
            case "slack":
                await this._connectSlack();
                break;
            case "github":
                await this._connectGitHub();
                break;
            case "confluence":
                await this._connectConfluence();
                break;
            case "teams":
                await this._connectTeams();
                break;
            case "zoom":
                await this._connectZoom();
                break;
            case "meet":
                await this._connectMeet();
                break;
            case "gitlab":
                await this._connectGeneric("gitlab");
                break;
            case "jenkins":
                await this._connectGeneric("jenkins");
                break;
            default:
                vscode.window.showWarningMessage(
                    `Connector '${connectorId}' is not yet implemented.`
                );
                return;
        }

        // After connecting, refresh status
        await this._handleGetStatus();
    }

    private async _handleAction(action: string, connectorId: string) {
        if (action === "sync") {
            await this._handleSync(connectorId);
            return;
        }
        if (action === "subscribe") {
            await this._handleSubscribe(connectorId);
            return;
        }
        if (action === "index") {
            await this._indexGitHubRepo();
            return;
        }
        await this._handleConnect(connectorId);
    }

    private async _handleSync(connectorId: string) {
        switch (connectorId) {
            case "slack":
                await this._syncSlack();
                break;
            case "confluence":
                await this._syncConfluence();
                break;
            case "zoom":
                await this._syncZoom();
                break;
            case "meet":
                await this._syncMeet();
                break;
            default:
                vscode.window.showWarningMessage(
                    `Sync is not yet implemented for ${connectorId}.`
                );
                return;
        }
    }

    private async _handleSubscribe(connectorId: string) {
        switch (connectorId) {
            case "confluence":
                await this._subscribeConfluence();
                break;
            case "teams":
                await this._subscribeTeams();
                break;
            case "meet":
                await this._subscribeMeet();
                break;
            default:
                vscode.window.showWarningMessage(
                    `Subscribe is not yet implemented for ${connectorId}.`
                );
                return;
        }
    }

    private async _startOAuthFlow(connectorId: string, path: string, label: string) {
        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}${path}?install=org`;

        try {
            const res = await fetch(url, {
                method: "GET",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
            });

            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`${label} OAuth start failed: ${errorText}`);
            }

            const json = (await res.json()) as any;
            if (!json?.auth_url) {
                throw new Error(`${label} OAuth did not return an auth_url`);
            }

            await vscode.env.openExternal(vscode.Uri.parse(json.auth_url));
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: { connectorId, ok: true },
            });
            vscode.window.showInformationMessage(
                `Complete ${label} OAuth in the browser, then return here to refresh status.`
            );
        } catch (err: any) {
            const msg = err?.message || String(err);
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId,
                    ok: false,
                    error: msg,
                },
            });
            vscode.window.showErrorMessage(`Failed to connect ${label}: ${msg}`);
        }
    }

    private async _connectConfluence() {
        await this._startOAuthFlow("confluence", "/api/connectors/confluence/oauth/start", "Confluence");
    }

    private async _connectTeams() {
        await this._startOAuthFlow("teams", "/api/connectors/teams/oauth/start", "Teams");
    }

    private async _connectZoom() {
        await this._startOAuthFlow("zoom", "/api/connectors/zoom/oauth/start", "Zoom");
    }

    private async _connectMeet() {
        await this._startOAuthFlow("meet", "/api/connectors/meet/oauth/start", "Google Meet");
    }

    private async _syncConfluence() {
        const spaceKey = await vscode.window.showInputBox({
            title: "Confluence space key",
            prompt: "Example: ENG",
            ignoreFocusOut: true,
        });
        if (!spaceKey) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "confluence", ok: false, error: "User cancelled" },
            });
            return;
        }

        const limitInput = await vscode.window.showInputBox({
            title: "Max pages to sync",
            prompt: "Default 20",
            ignoreFocusOut: true,
        });
        const limit = limitInput ? Math.min(Math.max(parseInt(limitInput, 10), 1), 200) : 20;

        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/confluence/sync`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({ space_key: spaceKey, limit }),
            });
            const json = (await res.json()) as any;
            const ok = res.ok && json?.processed_page_ids;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "confluence",
                    ok,
                    error: ok ? undefined : json?.detail || json?.error || "Sync failed",
                    details: ok ? `${json.total} pages` : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "confluence", ok: false, error: err?.message || String(err) },
            });
        }
    }

    private async _syncZoom() {
        const zoomUser = await vscode.window.showInputBox({
            title: "Zoom user email",
            prompt: "Email or user ID to sync recordings for",
            ignoreFocusOut: true,
        });
        if (!zoomUser) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "zoom", ok: false, error: "User cancelled" },
            });
            return;
        }

        const daysInput = await vscode.window.showInputBox({
            title: "Lookback window (days)",
            prompt: "Default 7",
            ignoreFocusOut: true,
        });
        const days = daysInput ? Math.min(Math.max(parseInt(daysInput, 10), 1), 90) : 7;
        const toDate = new Date();
        const fromDate = new Date();
        fromDate.setDate(toDate.getDate() - days);

        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/zoom/sync`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({
                    zoom_user: zoomUser,
                    from_date: fromDate.toISOString().slice(0, 10),
                    to_date: toDate.toISOString().slice(0, 10),
                    max_meetings: 20,
                }),
            });
            const json = (await res.json()) as any;
            const ok = res.ok && json?.processed_meeting_ids;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "zoom",
                    ok,
                    error: ok ? undefined : json?.detail || json?.error || "Sync failed",
                    details: ok ? `${json.total} meetings` : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "zoom", ok: false, error: err?.message || String(err) },
            });
        }
    }

    private async _syncMeet() {
        const calendarId = await vscode.window.showInputBox({
            title: "Google Calendar ID",
            prompt: "Default: primary",
            ignoreFocusOut: true,
        });
        const daysInput = await vscode.window.showInputBox({
            title: "Lookback window (days)",
            prompt: "Default 7",
            ignoreFocusOut: true,
        });
        const days = daysInput ? Math.min(Math.max(parseInt(daysInput, 10), 1), 90) : 7;

        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/meet/sync`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({
                    calendar_id: calendarId || "primary",
                    days_back: days,
                }),
            });
            const json = (await res.json()) as any;
            const ok = res.ok && json?.processed_event_ids;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "meet",
                    ok,
                    error: ok ? undefined : json?.detail || json?.error || "Sync failed",
                    details: ok ? `${json.total} events` : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "meet", ok: false, error: err?.message || String(err) },
            });
        }
    }

    private async _subscribeConfluence() {
        const spaceKey = await vscode.window.showInputBox({
            title: "Confluence space key (optional)",
            prompt: "Leave empty to subscribe to all spaces",
            ignoreFocusOut: true,
        });

        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/confluence/subscribe`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({ space_key: spaceKey || null }),
            });
            const json = (await res.json()) as any;
            const ok = res.ok && json?.ok;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "confluence",
                    ok,
                    error: ok ? undefined : json?.detail || json?.error || "Subscribe failed",
                    details: ok ? "webhook registered" : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "confluence", ok: false, error: err?.message || String(err) },
            });
        }
    }

    private async _subscribeTeams() {
        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";

        const teamsUrl = `${this._backendBaseUrl}/api/connectors/teams/teams`;
        const teamsRes = await fetch(teamsUrl, {
            method: "GET",
            headers: this._buildHeaders({
                "Content-Type": "application/json",
                "X-Org-Id": orgId,
            }),
        });
        if (!teamsRes.ok) {
            const text = await teamsRes.text();
            vscode.window.showErrorMessage(`Failed to list Teams: ${text}`);
            return;
        }
        const teamsJson = (await teamsRes.json()) as any;
        const teams = (teamsJson.items || []).map((t: any) => ({ label: t.display_name, id: t.id }));
        const teamPick = await vscode.window.showQuickPick<{ label: string; id: string }>(
            teams,
            { title: "Select a Team" }
        );
        if (!teamPick) {
            return;
        }

        const channelsUrl = `${this._backendBaseUrl}/api/connectors/teams/channels?team_id=${encodeURIComponent(teamPick.id)}`;
        const channelsRes = await fetch(channelsUrl, {
            method: "GET",
            headers: this._buildHeaders({
                "Content-Type": "application/json",
                "X-Org-Id": orgId,
            }),
        });
        if (!channelsRes.ok) {
            const text = await channelsRes.text();
            vscode.window.showErrorMessage(`Failed to list channels: ${text}`);
            return;
        }
        const channelsJson = (await channelsRes.json()) as any;
        const channels = (channelsJson.items || []).map((c: any) => ({ label: c.display_name, id: c.id }));
        const channelPick = await vscode.window.showQuickPick<{ label: string; id: string }>(
            channels,
            { title: "Select a Channel" }
        );
        if (!channelPick) {
            return;
        }

        const subscribeUrl = `${this._backendBaseUrl}/api/connectors/teams/subscribe`;
        const subscribeRes = await fetch(subscribeUrl, {
            method: "POST",
            headers: this._buildHeaders({
                "Content-Type": "application/json",
                "X-Org-Id": orgId,
            }),
            body: JSON.stringify({ team_id: teamPick.id, channel_id: channelPick.id }),
        });
        const subscribeJson = (await subscribeRes.json()) as any;
        const ok = subscribeRes.ok && subscribeJson?.ok;
        this._panel.webview.postMessage({
            type: "syncResult",
            payload: {
                connectorId: "teams",
                ok,
                error: ok ? undefined : subscribeJson?.detail || subscribeJson?.error || "Subscribe failed",
                details: ok ? "subscription created" : undefined,
            },
        });
    }

    private async _subscribeMeet() {
        const calendarId = await vscode.window.showInputBox({
            title: "Google Calendar ID",
            prompt: "Default: primary",
            ignoreFocusOut: true,
        });

        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/meet/subscribe`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({ calendar_id: calendarId || "primary" }),
            });
            const json = (await res.json()) as any;
            const ok = res.ok && json?.ok;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "meet",
                    ok,
                    error: ok ? undefined : json?.detail || json?.error || "Subscribe failed",
                    details: ok ? "watch registered" : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: { connectorId: "meet", ok: false, error: err?.message || String(err) },
            });
        }
    }

    private async _connectJira() {
        const baseUrl = await vscode.window.showInputBox({
            title: "Jira Cloud base URL",
            prompt: "Example: https://your-domain.atlassian.net",
            ignoreFocusOut: true,
            validateInput: (value) =>
                value.trim().length === 0 ? "Base URL is required" : undefined,
        });
        if (!baseUrl) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "jira",
                    ok: false,
                    error: "User cancelled",
                },
            });
            return;
        }

        const email = await vscode.window.showInputBox({
            title: "Jira email",
            prompt: "Email associated with your Jira account",
            ignoreFocusOut: true,
            validateInput: (value) =>
                value.trim().length === 0 ? "Email is required" : undefined,
        });
        if (!email) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "jira",
                    ok: false,
                    error: "User cancelled",
                },
            });
            return;
        }

        const apiToken = await vscode.window.showInputBox({
            title: "Jira API token",
            prompt: "Personal API token (will be sent to your local AEP backend)",
            password: true,
            ignoreFocusOut: true,
            validateInput: (value) =>
                value.trim().length === 0 ? "API token is required" : undefined,
        });
        if (!apiToken) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "jira",
                    ok: false,
                    error: "User cancelled",
                },
            });
            return;
        }

        const url = `${this._backendBaseUrl}/api/connectors/jira/connect`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({ "Content-Type": "application/json" }),
                body: JSON.stringify({
                    base_url: baseUrl,
                    email,
                    api_token: apiToken,
                }),
            });

            const json = await res.json() as any;
            const ok = res.ok && json.ok !== false;

            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "jira",
                    ok,
                    error: ok ? undefined : json.detail || json.error || "Failed to connect",
                },
            });

            if (!ok) {
                vscode.window.showErrorMessage(
                    `Failed to connect Jira: ${json.detail || json.error || "Unknown error"}`
                );
            }
        } catch (err: any) {
            const msg = err?.message || String(err);
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "jira",
                    ok: false,
                    error: msg,
                },
            });
            vscode.window.showErrorMessage(`Failed to connect Jira: ${msg}`);
        }
    }

    private async _connectSlack() {
        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/slack/oauth/start?install=org`;

        try {
            const res = await fetch(url, {
                method: "GET",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
            });

            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`Slack OAuth start failed: ${errorText}`);
            }

            const json = (await res.json()) as any;
            if (!json?.auth_url) {
                throw new Error("Slack OAuth did not return an auth_url");
            }
            await vscode.env.openExternal(vscode.Uri.parse(json.auth_url));
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: { connectorId: "slack", ok: true },
            });
            vscode.window.showInformationMessage(
                "Complete Slack OAuth in the browser, then return here to refresh status."
            );
        } catch (err: any) {
            const msg = err?.message || String(err);
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "slack",
                    ok: false,
                    error: msg,
                },
            });
            vscode.window.showErrorMessage(`Failed to connect Slack: ${msg}`);
        }
    }

    private async _syncSlack() {
        const channelsInput = await vscode.window.showInputBox({
            title: "Slack channels to sync",
            prompt: "Comma-separated channel names (e.g., eng-backend, general)",
            ignoreFocusOut: true,
        });

        if (!channelsInput) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "slack",
                    ok: false,
                    error: "User cancelled",
                },
            });
            return;
        }

        const channels = channelsInput
            .split(",")
            .map((c) => c.trim())
            .filter(Boolean);

        if (channels.length === 0) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "slack",
                    ok: false,
                    error: "Provide at least one channel name",
                },
            });
            return;
        }

        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/slack/sync`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({ channels, limit: 200 }),
            });

            const json = (await res.json()) as any;
            const ok = res.ok && json?.processed_channel_ids;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "slack",
                    ok,
                    error: ok ? undefined : json?.detail || json?.error || "Sync failed",
                    details: ok ? `${json.total} channels` : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "slack",
                    ok: false,
                    error: err?.message || String(err),
                },
            });
        }
    }

    private async _connectGitHub() {
        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const url = `${this._backendBaseUrl}/api/connectors/github/oauth/start?install=org`;

        try {
            const res = await fetch(url, {
                method: "GET",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
            });

            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`GitHub OAuth start failed: ${errorText}`);
            }

            const json = (await res.json()) as any;
            if (!json?.auth_url) {
                throw new Error("GitHub OAuth did not return an auth_url");
            }

            await vscode.env.openExternal(vscode.Uri.parse(json.auth_url));
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: { connectorId: "github", ok: true },
            });
            vscode.window.showInformationMessage(
                "Complete GitHub OAuth in the browser, then return here to refresh status."
            );
        } catch (err: any) {
            const msg = err?.message || String(err);
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "github",
                    ok: false,
                    error: msg,
                },
            });
            vscode.window.showErrorMessage(`Failed to connect GitHub: ${msg}`);
        }
    }

    private async _indexGitHubRepo() {
        const config = vscode.workspace.getConfiguration("aep");
        const orgId = config.get<string>("navi.orgId") || "default";
        const listUrl = `${this._backendBaseUrl}/api/connectors/github/repos`;

        try {
            const res = await fetch(listUrl, {
                method: "GET",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
            });
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(`Failed to list repos: ${errText}`);
            }
            const json = (await res.json()) as any;
            const repos = (json.items || []).map((r: any) => r.full_name).filter(Boolean);
            if (repos.length === 0) {
                throw new Error("No repositories available for this GitHub connection");
            }

            const choice = await vscode.window.showQuickPick(repos, {
                title: "Select a GitHub repo to index",
                canPickMany: false,
            });
            if (!choice) {
                this._panel.webview.postMessage({
                    type: "syncResult",
                    payload: { connectorId: "github", ok: false, error: "User cancelled" },
                });
                return;
            }

            const indexUrl = `${this._backendBaseUrl}/api/connectors/github/index`;
            const indexRes = await fetch(indexUrl, {
                method: "POST",
                headers: this._buildHeaders({
                    "Content-Type": "application/json",
                    "X-Org-Id": orgId,
                }),
                body: JSON.stringify({ repo_full_name: choice }),
            });
            const indexJson = (await indexRes.json()) as any;
            const ok = indexRes.ok && indexJson?.ok;
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "github",
                    ok,
                    error: ok ? undefined : indexJson?.detail || indexJson?.error || "Index failed",
                    details: ok ? "Index queued" : undefined,
                },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "syncResult",
                payload: {
                    connectorId: "github",
                    ok: false,
                    error: err?.message || String(err),
                },
            });
        }
    }

    private async _connectGeneric(provider: string) {
        const baseUrl = await vscode.window.showInputBox({
            title: `${provider} base URL`,
            prompt: provider === "github" ? "https://api.github.com (or enterprise API root)" : "Base API URL",
            value: provider === "github" ? "https://api.github.com" : undefined,
            ignoreFocusOut: true,
        });
        if (!baseUrl) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: { connectorId: provider, ok: false, error: "User cancelled" },
            });
            return;
        }

        const token = await vscode.window.showInputBox({
            title: `${provider} token`,
            prompt: `Personal access token for ${provider}`,
            password: true,
            ignoreFocusOut: true,
            validateInput: (v) => (v.trim().length === 0 ? "Token is required" : undefined),
        });
        if (!token) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: { connectorId: provider, ok: false, error: "User cancelled" },
            });
            return;
        }

        const url = `${this._backendBaseUrl}/api/connectors/save`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: this._buildHeaders({ "Content-Type": "application/json" }),
                body: JSON.stringify({
                    provider,
                    base_url: baseUrl,
                    token,
                    name: "default",
                }),
            });

            if (!res.ok) {
                const errText = await res.text();
                throw new Error(`HTTP ${res.status} ${res.statusText}: ${errText}`);
            }

            this._panel.webview.postMessage({
                type: "connectResult",
                payload: { connectorId: provider, ok: true },
            });
        } catch (err: any) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: provider,
                    ok: false,
                    error: err?.message || String(err),
                },
            });
        }
    }

    // -----------------------------------------------------------------------
    // HTML + webview assets
    // -----------------------------------------------------------------------

    private _getHtmlForWebview(webview: vscode.Webview): string {
        // Add cache busting timestamp
        const cacheBust = Date.now();
        const authToken = this._getAuthToken() || "";

        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, "media", "connectorsPanel.js")
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, "media", "panel.css")
        );
        const iconBaseUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, "media", "icons")
        );

        const cspSource = webview.cspSource;

        return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; img-src ${cspSource} https: data:; style-src ${cspSource} 'unsafe-inline'; script-src ${cspSource}; connect-src http://127.0.0.1:8788 http://localhost:8788;">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="${styleUri}?v=${cacheBust}" rel="stylesheet" />
  <title>Connections</title>
</head>
<body class="aep-theme">
  <div id="root"></div>

  <script>
    window.AEP_CONNECTOR_ICON_BASE = "${iconBaseUri}";
    console.log("[AEP] Connectors panel loaded, cache bust: ${cacheBust}");
    console.log("[AEP] Icon base URI:", "${iconBaseUri}");
    console.log("[AEP] Testing fetch capability...");
    
    // Immediate test to see if webview can make requests
    const authToken = ${JSON.stringify(authToken)};
        const authHeader = authToken
            ? (authToken.startsWith("Bearer ") ? authToken : "Bearer " + authToken)
            : "";
    const headers = authHeader ? { Authorization: authHeader } : {};
    fetch("http://127.0.0.1:8000/api/connectors/marketplace/status", { headers })
      .then(r => {
        console.log("[AEP] Immediate fetch test - status:", r.status);
        return r.json();
      })
      .then(data => console.log("[AEP] Immediate fetch test - data:", data))
      .catch(err => console.error("[AEP] Immediate fetch test - error:", err));
  </script>
  <script src="${scriptUri}?v=${cacheBust}"></script>
</body>
</html>`;
    }
}
