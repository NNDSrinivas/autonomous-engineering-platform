// connectorsPanel.ts
// Webview panel for managing connector integrations (Jira, Slack, Teams, etc.)

import * as vscode from 'vscode';

function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}

export class ConnectorsPanel {
    public static currentPanel: ConnectorsPanel | undefined;

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private readonly _backendBaseUrl: string;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(
        extensionUri: vscode.Uri,
        backendBaseUrl: string,
        context: vscode.ExtensionContext
    ) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : vscode.ViewColumn.One;

        // If we already have a panel, just reveal it
        if (ConnectorsPanel.currentPanel) {
            console.log('[ConnectorsPanel] Panel already exists, revealing it');
            ConnectorsPanel.currentPanel._panel.reveal(column);
            return;
        }

        console.log('[ConnectorsPanel] Creating new panel with baseUrl:', backendBaseUrl);
        const panel = vscode.window.createWebviewPanel(
            'aepConnectors',
            'NAVI — Connectors',
            vscode.ViewColumn.Two, // Open in second column to avoid overlap
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')],
            }
        );

        console.log('[ConnectorsPanel] Panel created, initializing ConnectorsPanel class');
        ConnectorsPanel.currentPanel = new ConnectorsPanel(
            panel,
            extensionUri,
            backendBaseUrl
        );
        console.log('[ConnectorsPanel] ConnectorsPanel initialization complete');
    }

    private constructor(
        panel: vscode.WebviewPanel,
        extensionUri: vscode.Uri,
        backendBaseUrl: string
    ) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._backendBaseUrl = backendBaseUrl;

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.html = this._getHtmlForWebview(
            this._panel.webview,
            backendBaseUrl
        );

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case 'closePanel': {
                        this._panel.dispose();
                        break;
                    }
                    case 'openExternal': {
                        const url = String(message.url || '').trim();
                        if (!url) return;
                        try {
                            await vscode.env.openExternal(vscode.Uri.parse(url));
                        } catch (e) {
                            vscode.window.showErrorMessage('Failed to open external URL');
                        }
                        break;
                    }
                    case 'showToast': {
                        const msg = String(message.message || '').trim();
                        const level = String(message.level || 'info');
                        if (!msg) return;

                        switch (level) {
                            case 'error':
                                vscode.window.showErrorMessage(`NAVI: ${msg}`);
                                break;
                            case 'warning':
                                vscode.window.showWarningMessage(`NAVI: ${msg}`);
                                break;
                            default:
                                vscode.window.showInformationMessage(`NAVI: ${msg}`);
                        }
                        break;
                    }
                    case 'connectors.getStatus': {
                        // Proxy connector status request to backend
                        try {
                            const response = await fetch(`${this._backendBaseUrl}/api/connectors/status`);
                            if (!response.ok) {
                                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                            }
                            const data = await response.json();
                            this._panel.webview.postMessage({ type: 'connectors.status', data });
                        } catch (err: any) {
                            console.error('[ConnectorsPanel] Status error:', err);
                            this._panel.webview.postMessage({
                                type: 'connectors.statusError',
                                error: err?.message || String(err),
                            });
                        }
                        break;
                    }
                    case 'connectors.jiraConnect': {
                        // Proxy Jira connection request to backend
                        try {
                            const endpoint = `${this._backendBaseUrl}/api/connectors/jira/connect`;

                            console.log('[ConnectorsPanel] Jira connect - Backend base URL:', backendBaseUrl);
                            console.log('[ConnectorsPanel] Jira connect - Full endpoint:', endpoint);
                            console.log('[ConnectorsPanel] Jira connect - Request payload:', {
                                base_url: message.baseUrl,
                                email: message.email || undefined,
                                api_token: message.apiToken ? '***' : undefined
                            });

                            const response = await fetch(endpoint, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    base_url: message.baseUrl,
                                    email: message.email || undefined,
                                    api_token: message.apiToken,
                                }),
                            });

                            console.log('[ConnectorsPanel] Jira connect - Response status:', response.status);

                            if (!response.ok) {
                                const errorText = await response.text().catch(() => '');
                                console.error('[ConnectorsPanel] Jira connect - Error response:', errorText);
                                throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
                            }

                            const data = await response.json() as { status?: string;[key: string]: any };
                            console.log('[ConnectorsPanel] Jira connect - Success response:', data);

                            // Send proper result message
                            this._panel.webview.postMessage({
                                type: 'connectors.jiraConnect.result',
                                ok: true,
                                provider: 'jira',
                                status: data.status || 'connected',
                                data
                            });
                        } catch (err: any) {
                            console.error('[ConnectorsPanel] Jira connect error:', err);
                            console.error('[ConnectorsPanel] Error stack:', err.stack);

                            // Send proper error result message
                            this._panel.webview.postMessage({
                                type: 'connectors.jiraConnect.result',
                                ok: false,
                                provider: 'jira',
                                error: err?.message || String(err),
                            });
                        }
                        break;
                    }
                }
            },
            null,
            this._disposables
        );
    }

    public dispose() {
        ConnectorsPanel.currentPanel = undefined;

        this._panel.dispose();

        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) {
                d.dispose();
            }
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview, backendBaseUrl: string) {
        const nonce = getNonce();

        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'connectorsPanel.js')
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.css')
        );
        const iconsUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'icons')
        );

        return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; img-src ${webview.cspSource} https: data:; script-src 'nonce-${nonce}'; style-src ${webview.cspSource} 'unsafe-inline'; connect-src https: http:;" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link href="${styleUri}" rel="stylesheet" />
  <title>NAVI Connectors</title>
  <script nonce="${nonce}">
    window.AEP_CONFIG = {
      backendBaseUrl: "${backendBaseUrl}",
      iconsUri: "${iconsUri}"
    };
    window.vscode = acquireVsCodeApi();
  </script>
</head>
<body style="margin: 0; padding: 0; background: var(--vscode-editor-background); color: var(--vscode-editor-foreground);">
  <!-- Connectors Hub UI -->
  <div id="aep-connectors-container" style="display: flex; flex-direction: column; height: 100vh;">
    <div style="padding: 24px 24px 16px; border-bottom: 1px solid rgba(75, 85, 99, 0.3);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.02em;">Connectors Hub</h2>
        <button id="aep-connections-close" style="background: transparent; border: none; color: var(--vscode-foreground); cursor: pointer; font-size: 20px; padding: 4px 8px; opacity: 0.7;" title="Close">✕</button>
      </div>
      <p style="margin: 0 0 16px 0; font-size: 13px; color: var(--vscode-descriptionForeground); line-height: 1.5;">
        Connect Jira, Slack, Teams, Zoom, GitHub, Jenkins and more so NAVI can use full organizational context.
      </p>

      <div class="aep-search-bar" style="position: relative;">
        <input 
          type="text" 
          id="aep-connectors-search" 
          class="aep-input" 
          placeholder="Search connectors..." 
          style="padding-left: 36px;"
        />
        <svg style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; opacity: 0.5;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>

      <div id="aep-connectors-filters" class="aep-filters" style="margin-top: 16px;"></div>
    </div>

    <div id="aep-connectors-list" class="aep-connectors-list" style="flex: 1; overflow-y: auto;"></div>
  </div>

  <script src="${scriptUri}" nonce="${nonce}"></script>
</body>
</html>`;
    }
}
