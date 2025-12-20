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
        const naviBackendUrl = config.get<string>("navi.backendUrl") || "http://127.0.0.1:8787";

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
                headers: {
                    "Content-Type": "application/json",
                    "User-Agent": "VSCode-AEP-Extension/1.0"
                },
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
                await this._connectGeneric("github");
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
                headers: { "Content-Type": "application/json" },
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
        const botToken = await vscode.window.showInputBox({
            title: "Slack bot token",
            prompt: "Paste your Slack bot token (xoxb-…)",
            password: true,
            ignoreFocusOut: true,
            validateInput: (value) =>
                value.trim().length === 0 ? "Bot token is required" : undefined,
        });

        if (!botToken) {
            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "slack",
                    ok: false,
                    error: "User cancelled",
                },
            });
            return;
        }

        const url = `${this._backendBaseUrl}/api/connectors/slack/connect`;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ bot_token: botToken }),
            });

            const json = await res.json() as any;
            const ok = res.ok && json.ok !== false;

            this._panel.webview.postMessage({
                type: "connectResult",
                payload: {
                    connectorId: "slack",
                    ok,
                    error: ok ? undefined : json.detail || json.error || "Failed to connect",
                },
            });

            if (!ok) {
                vscode.window.showErrorMessage(
                    `Failed to connect Slack: ${json.detail || json.error || "Unknown error"}`
                );
            }
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
                headers: { "Content-Type": "application/json" },
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
    content="default-src 'none'; img-src ${cspSource} https: data:; style-src ${cspSource} 'unsafe-inline'; script-src ${cspSource}; connect-src http://127.0.0.1:8787 http://localhost:8787;">
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
    fetch("http://127.0.0.1:8787/api/connectors/marketplace/status")
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
