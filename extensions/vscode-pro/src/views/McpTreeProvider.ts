import * as vscode from 'vscode';

export class McpTreeProvider implements vscode.TreeDataProvider<McpItem> {
    private emitter = new vscode.EventEmitter<McpItem | undefined>();
    readonly onDidChangeTreeData = this.emitter.event;

    getTreeItem(element: McpItem): vscode.TreeItem {
        return element;
    }

    getChildren(): McpItem[] {
        const cfg = vscode.workspace.getConfiguration('aep');
        const servers: Array<{ name: string; url: string; token?: string }> = cfg.get('mcp.servers') ?? [];
        return servers.map(server => new McpItem(server.name, server.url, server.token));
    }

    async addServer(): Promise<void> {
        try {
            const name = await vscode.window.showInputBox({
                prompt: '🏷️ Enter MCP server name',
                placeHolder: 'e.g. "Local MCP Server"',
                validateInput: (value) => {
                    if (!value || value.trim().length === 0) {
                        return 'Server name is required';
                    }
                    return undefined;
                }
            });

            if (!name) return;

            const url = await vscode.window.showInputBox({
                prompt: '🌐 Enter MCP server URL',
                placeHolder: 'e.g. "http://localhost:3000" or "https://api.example.com"',
                validateInput: (value) => {
                    if (!value || value.trim().length === 0) {
                        return 'Server URL is required';
                    }
                    try {
                        new URL(value.trim());
                        return undefined;
                    } catch {
                        return 'Please enter a valid URL';
                    }
                }
            });

            if (!url) return;

            const token = await vscode.window.showInputBox({
                prompt: '🔑 Enter authentication token (optional)',
                placeHolder: 'Leave empty if no authentication required',
                password: true
            });

            const cfg = vscode.workspace.getConfiguration('aep');
            const servers: Array<{ name: string; url: string; token?: string }> = cfg.get('mcp.servers') ?? [];

            const newServer = {
                name: name.trim(),
                url: url.trim(),
                ...(token?.trim() && { token: token.trim() })
            };

            servers.push(newServer);
            await cfg.update('mcp.servers', servers, vscode.ConfigurationTarget.Global);

            this.emitter.fire(undefined);
            vscode.window.showInformationMessage(`✅ Added MCP server "${name}"`);
        } catch (error: any) {
            vscode.window.showErrorMessage(`❌ Failed to add MCP server: ${error?.message || String(error)}`);
        }
    }

    async removeServer(item: McpItem): Promise<void> {
        try {
            const result = await vscode.window.showWarningMessage(
                `Are you sure you want to remove MCP server "${item.label}"?`,
                { modal: true },
                'Remove'
            );

            if (result !== 'Remove') return;

            const cfg = vscode.workspace.getConfiguration('aep');
            const servers: Array<{ name: string; url: string; token?: string }> = cfg.get('mcp.servers') ?? [];

            const filteredServers = servers.filter(s => s.name !== item.label || s.url !== item.url);
            await cfg.update('mcp.servers', filteredServers, vscode.ConfigurationTarget.Global);

            this.emitter.fire(undefined);
            vscode.window.showInformationMessage(`🗑️ Removed MCP server "${item.label}"`);
        } catch (error: any) {
            vscode.window.showErrorMessage(`❌ Failed to remove MCP server: ${error?.message || String(error)}`);
        }
    }

    async testServer(item?: McpItem): Promise<void> {
        if (!item?.url) {
            vscode.window.showErrorMessage('❌ No server URL to test');
            return;
        }

        const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left);
        statusItem.text = `$(loading~spin) Testing ${item.label}...`;
        statusItem.show();

        try {
            const headers: Record<string, string> = {
                'User-Agent': 'AEP-VSCode-Extension/2.0.0'
            };

            if (item.token) {
                headers['Authorization'] = `Bearer ${item.token}`;
            }

            const response = await fetch(item.url, {
                method: 'GET',
                headers
            });

            statusItem.hide();
            statusItem.dispose();

            if (response.ok) {
                vscode.window.showInformationMessage(
                    `✅ MCP server "${item.label}" is reachable (Status: ${response.status})`
                );
            } else {
                vscode.window.showWarningMessage(
                    `⚠️ MCP server "${item.label}" returned status ${response.status}`
                );
            }
        } catch (error: any) {
            statusItem.hide();
            statusItem.dispose();

            vscode.window.showErrorMessage(
                `❌ Failed to connect to MCP server "${item.label}": ${error?.message || 'Connection failed'}`
            );
        }
    }

    refresh(): void {
        this.emitter.fire(undefined);
    }
}

class McpItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly url: string,
        public readonly token?: string
    ) {
        super(label, vscode.TreeItemCollapsibleState.None);
        this.description = url;
        this.contextValue = 'mcpServer';
        this.tooltip = `${label}\n${url}${token ? '\n🔒 Authenticated' : '\n🔓 No authentication'}`;

        // Set icon based on URL protocol
        if (url.startsWith('https://')) {
            this.iconPath = new vscode.ThemeIcon('lock', new vscode.ThemeColor('charts.green'));
        } else if (url.startsWith('http://')) {
            this.iconPath = new vscode.ThemeIcon('unlock', new vscode.ThemeColor('charts.yellow'));
        } else {
            this.iconPath = new vscode.ThemeIcon('server-environment');
        }

        // Add command to test server on click
        this.command = {
            command: 'aep.mcp.testServer',
            title: 'Test MCP Server',
            arguments: [this]
        };
    }
}