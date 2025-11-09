"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.McpTreeProvider = void 0;
const vscode = __importStar(require("vscode"));
class McpTreeProvider {
    constructor() {
        this.emitter = new vscode.EventEmitter();
        this.onDidChangeTreeData = this.emitter.event;
    }
    getTreeItem(element) {
        return element;
    }
    getChildren() {
        const cfg = vscode.workspace.getConfiguration('aep');
        const servers = cfg.get('mcp.servers') ?? [];
        return servers.map(server => new McpItem(server.name, server.url, server.token));
    }
    async addServer() {
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
            if (!name)
                return;
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
                    }
                    catch {
                        return 'Please enter a valid URL';
                    }
                }
            });
            if (!url)
                return;
            const token = await vscode.window.showInputBox({
                prompt: '🔑 Enter authentication token (optional)',
                placeHolder: 'Leave empty if no authentication required',
                password: true
            });
            const cfg = vscode.workspace.getConfiguration('aep');
            const servers = cfg.get('mcp.servers') ?? [];
            const newServer = {
                name: name.trim(),
                url: url.trim(),
                ...(token?.trim() && { token: token.trim() })
            };
            servers.push(newServer);
            await cfg.update('mcp.servers', servers, vscode.ConfigurationTarget.Global);
            this.emitter.fire(undefined);
            vscode.window.showInformationMessage(`✅ Added MCP server "${name}"`);
        }
        catch (error) {
            vscode.window.showErrorMessage(`❌ Failed to add MCP server: ${error?.message || String(error)}`);
        }
    }
    async removeServer(item) {
        try {
            const result = await vscode.window.showWarningMessage(`Are you sure you want to remove MCP server "${item.label}"?`, { modal: true }, 'Remove');
            if (result !== 'Remove')
                return;
            const cfg = vscode.workspace.getConfiguration('aep');
            const servers = cfg.get('mcp.servers') ?? [];
            const filteredServers = servers.filter(s => s.name !== item.label || s.url !== item.url);
            await cfg.update('mcp.servers', filteredServers, vscode.ConfigurationTarget.Global);
            this.emitter.fire(undefined);
            vscode.window.showInformationMessage(`🗑️ Removed MCP server "${item.label}"`);
        }
        catch (error) {
            vscode.window.showErrorMessage(`❌ Failed to remove MCP server: ${error?.message || String(error)}`);
        }
    }
    async testServer(item) {
        if (!item?.url) {
            vscode.window.showErrorMessage('❌ No server URL to test');
            return;
        }
        const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left);
        statusItem.text = `$(loading~spin) Testing ${item.label}...`;
        statusItem.show();
        try {
            const headers = {
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
                vscode.window.showInformationMessage(`✅ MCP server "${item.label}" is reachable (Status: ${response.status})`);
            }
            else {
                vscode.window.showWarningMessage(`⚠️ MCP server "${item.label}" returned status ${response.status}`);
            }
        }
        catch (error) {
            statusItem.hide();
            statusItem.dispose();
            vscode.window.showErrorMessage(`❌ Failed to connect to MCP server "${item.label}": ${error?.message || 'Connection failed'}`);
        }
    }
    refresh() {
        this.emitter.fire(undefined);
    }
}
exports.McpTreeProvider = McpTreeProvider;
class McpItem extends vscode.TreeItem {
    constructor(label, url, token) {
        super(label, vscode.TreeItemCollapsibleState.None);
        this.label = label;
        this.url = url;
        this.token = token;
        this.description = url;
        this.contextValue = 'mcpServer';
        this.tooltip = `${label}\n${url}${token ? '\n🔒 Authenticated' : '\n🔓 No authentication'}`;
        // Set icon based on URL protocol
        if (url.startsWith('https://')) {
            this.iconPath = new vscode.ThemeIcon('lock', new vscode.ThemeColor('charts.green'));
        }
        else if (url.startsWith('http://')) {
            this.iconPath = new vscode.ThemeIcon('unlock', new vscode.ThemeColor('charts.yellow'));
        }
        else {
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
//# sourceMappingURL=McpTreeProvider.js.map