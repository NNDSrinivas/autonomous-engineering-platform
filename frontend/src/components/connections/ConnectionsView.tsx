import React, { useState } from "react";
import "./ConnectionsView.css";

type ConnectorKind = "github" | "gitlab" | "jira" | "slack" | "confluence" | "ci";

interface Connector {
    id: string;
    kind: ConnectorKind;
    name: string;
    description: string;
    connected: boolean;
    canWrite: boolean;
    scope: string;
}

interface McpServer {
    id: string;
    name: string;
    url: string;
    status: "online" | "offline" | "error";
    latencyMs: number | null;
    source: "local" | "remote";
    tools: string[];
}

const INITIAL_CONNECTORS: Connector[] = [
    {
        id: "github-main",
        kind: "github",
        name: "GitHub",
        description: "Repositories, PRs, branches, checks",
        connected: true,
        canWrite: true,
        scope: "NavraLabs org",
    },
    {
        id: "jira-main",
        kind: "jira",
        name: "Jira",
        description: "Issues, sprints, epics",
        connected: true,
        canWrite: true,
        scope: "AEP project",
    },
    {
        id: "ci-gha",
        kind: "ci",
        name: "GitHub Actions",
        description: "Builds, workflows, artifacts",
        connected: true,
        canWrite: false,
        scope: "AEP repo",
    },
    {
        id: "slack-main",
        kind: "slack",
        name: "Slack",
        description: "Channels, threads, mentions",
        connected: false,
        canWrite: false,
        scope: "Workspace (not connected)",
    },
    {
        id: "confluence-main",
        kind: "confluence",
        name: "Confluence",
        description: "Specs, ADRs, runbooks",
        connected: false,
        canWrite: false,
        scope: "Docs space (not connected)",
    },
];

const INITIAL_MCP_SERVERS: McpServer[] = [
    {
        id: "mcp-jira",
        name: "Jira MCP",
        url: "http://localhost:9001",
        status: "online",
        latencyMs: 42,
        source: "local",
        tools: ["listIssues", "getIssue", "createIssue"],
    },
    {
        id: "mcp-github",
        name: "GitHub MCP",
        url: "http://localhost:9002",
        status: "online",
        latencyMs: 55,
        source: "local",
        tools: ["listRepos", "getRepo", "createPullRequest"],
    },
    {
        id: "mcp-slack",
        name: "Slack MCP",
        url: "https://mcp.navralabs.com/slack",
        status: "offline",
        latencyMs: null,
        source: "remote",
        tools: ["listChannels", "postMessage"],
    },
];

export default function ConnectionsView() {
    const [connectors, setConnectors] = useState<Connector[]>(INITIAL_CONNECTORS);
    const [mcpServers, setMcpServers] = useState<McpServer[]>(INITIAL_MCP_SERVERS);
    const [activeTab, setActiveTab] = useState<"connectors" | "mcp" | "policies">(
        "connectors"
    );

    const toggleConnectorConnected = (id: string) => {
        setConnectors((prev) =>
            prev.map((c) =>
                c.id === id ? { ...c, connected: !c.connected } : c
            )
        );
    };

    const toggleConnectorWrite = (id: string) => {
        setConnectors((prev) =>
            prev.map((c) =>
                c.id === id ? { ...c, canWrite: !c.canWrite } : c
            )
        );
    };

    const refreshMcp = (id: string) => {
        // For now just fake a refresh; wire to backend later
        setMcpServers((prev) =>
            prev.map((s) =>
                s.id === id
                    ? {
                        ...s,
                        status: "online",
                        latencyMs: 40 + Math.round(Math.random() * 20),
                    }
                    : s
            )
        );
    };

    return (
        <div className="navi-connections-root">
            <div className="navi-connections-header">
                <div>
                    <h2 className="navi-connections-title">Connections</h2>
                    <p className="navi-connections-subtitle">
                        Control which systems Navi can see and what it's allowed to change.
                    </p>
                </div>

                <button
                    type="button"
                    className="navi-connections-add-btn"
                    onClick={() => {
                        // stub; later open "Add connector" modal
                        alert("Add new connector / MCP server (to be implemented).");
                    }}
                >
                    + Add
                </button>
            </div>

            <div className="navi-connections-tabs">
                <button
                    type="button"
                    className={
                        "navi-connections-tab" +
                        (activeTab === "connectors" ? " navi-connections-tab--active" : "")
                    }
                    onClick={() => setActiveTab("connectors")}
                >
                    Connectors
                </button>
                <button
                    type="button"
                    className={
                        "navi-connections-tab" +
                        (activeTab === "mcp" ? " navi-connections-tab--active" : "")
                    }
                    onClick={() => setActiveTab("mcp")}
                >
                    MCP Servers
                </button>
                <button
                    type="button"
                    className={
                        "navi-connections-tab" +
                        (activeTab === "policies" ? " navi-connections-tab--active" : "")
                    }
                    onClick={() => setActiveTab("policies")}
                >
                    Org policies
                </button>
            </div>

            {activeTab === "connectors" && (
                <div className="navi-connections-section">
                    {connectors.map((c) => (
                        <div key={c.id} className="navi-connector-card">
                            <div className="navi-connector-main">
                                <div className="navi-connector-icon">{c.name[0]}</div>
                                <div>
                                    <div className="navi-connector-title-row">
                                        <span className="navi-connector-name">{c.name}</span>
                                        <span
                                            className={
                                                "navi-connector-status-dot" +
                                                (c.connected ? " navi-connector-status-dot--on" : "")
                                            }
                                        />
                                        <span className="navi-connector-status-text">
                                            {c.connected ? "Connected" : "Not connected"}
                                        </span>
                                    </div>
                                    <p className="navi-connector-description">{c.description}</p>
                                    <p className="navi-connector-scope">Scope: {c.scope}</p>
                                </div>
                            </div>

                            <div className="navi-connector-actions">
                                <label className="navi-connector-toggle">
                                    <input
                                        type="checkbox"
                                        checked={c.connected}
                                        onChange={() => toggleConnectorConnected(c.id)}
                                    />
                                    <span>Enable for Navi</span>
                                </label>

                                <label className="navi-connector-toggle">
                                    <input
                                        type="checkbox"
                                        checked={c.canWrite}
                                        disabled={!c.connected}
                                        onChange={() => toggleConnectorWrite(c.id)}
                                    />
                                    <span>Allow writes (PRs, tickets, posts)</span>
                                </label>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {activeTab === "mcp" && (
                <div className="navi-connections-section">
                    {mcpServers.map((s) => (
                        <div key={s.id} className="navi-mcp-card">
                            <div className="navi-mcp-main">
                                <div className="navi-mcp-title-row">
                                    <span className="navi-mcp-name">{s.name}</span>
                                    <span
                                        className={
                                            "navi-mcp-status-dot" +
                                            (s.status === "online"
                                                ? " navi-mcp-status-dot--on"
                                                : s.status === "error"
                                                    ? " navi-mcp-status-dot--error"
                                                    : "")
                                        }
                                    />
                                    <span className="navi-mcp-status-text">
                                        {s.status === "online"
                                            ? "Online"
                                            : s.status === "offline"
                                                ? "Offline"
                                                : "Error"}
                                    </span>
                                    {s.latencyMs != null && (
                                        <span className="navi-mcp-latency">
                                            {s.latencyMs} ms
                                        </span>
                                    )}
                                </div>
                                <p className="navi-mcp-url">{s.url}</p>
                                <p className="navi-mcp-tools">
                                    Tools: {s.tools.join(", ")}
                                </p>
                            </div>

                            <div className="navi-mcp-actions">
                                <span className="navi-mcp-source">{s.source}</span>
                                <button
                                    type="button"
                                    className="navi-mcp-refresh-btn"
                                    onClick={() => refreshMcp(s.id)}
                                >
                                    Test / refresh
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {activeTab === "policies" && (
                <div className="navi-connections-section">
                    <div className="navi-policies-card">
                        <h3 className="navi-policies-title">Autonomy policies (mock)</h3>
                        <p className="navi-policies-text">
                            Here you'll be able to define org-wide rules for what Navi is
                            allowed to do automatically (open PRs, merge, file tickets,
                            post to Slack, etc.) based on branch, repo, and environment.
                        </p>
                        <ul className="navi-policies-list">
                            <li>🔒 Safe: propose diffs only, never write externally.</li>
                            <li>⚖️ Balanced: can open PRs and tickets, cannot merge.</li>
                            <li>🚀 Aggressive: can auto-merge when tests pass (within rules).</li>
                        </ul>
                    </div>
                </div>
            )}
        </div>
    );
}
