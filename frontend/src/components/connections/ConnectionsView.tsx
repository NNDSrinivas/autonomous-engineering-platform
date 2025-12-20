import React, { useEffect, useState } from "react";
import { api, ORG, USER_ID } from "../../api/client";
import { useWorkspace } from "../../context/WorkspaceContext";
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
    const { workspaceRoot } = useWorkspace();
    const [connectors, setConnectors] = useState<Connector[]>(INITIAL_CONNECTORS);
    const [mcpServers, setMcpServers] = useState<McpServer[]>(INITIAL_MCP_SERVERS);
    const [activeTab, setActiveTab] = useState<"connectors" | "mcp" | "policies">(
        "connectors"
    );
    const [policyCoverage, setPolicyCoverage] = useState<string>("80");
    const [policyUserId, setPolicyUserId] = useState<string>(USER_ID);
    const [policyLoading, setPolicyLoading] = useState(false);
    const [policySaving, setPolicySaving] = useState(false);
    const [policyError, setPolicyError] = useState<string | null>(null);
    const [policyStatus, setPolicyStatus] = useState<string | null>(null);
    const [scanStatus, setScanStatus] = useState<any | null>(null);
    const [scanLoading, setScanLoading] = useState(false);
    const [scanError, setScanError] = useState<string | null>(null);
    const [scanNotice, setScanNotice] = useState<string | null>(null);
    const [scanAllowSecrets, setScanAllowSecrets] = useState(false);
    const [connectorSyncing, setConnectorSyncing] = useState<string | null>(null);
    const [syncAllLoading, setSyncAllLoading] = useState(false);

    const loadScanStatus = async () => {
        setScanError(null);
        try {
            const effectiveUserId = policyUserId.trim() || USER_ID;
            const response = await api.get("/api/org/scan/status", {
                headers: { "X-User-Id": effectiveUserId },
            });
            const data = response.data || {};
            setScanStatus(data);
            setScanAllowSecrets(Boolean(data.allow_secrets));
        } catch {
            setScanError("Failed to load scan status.");
        }
    };

    useEffect(() => {
        if (activeTab !== "policies") return;

        let cancelled = false;
        setPolicyLoading(true);
        setPolicyError(null);
        setPolicyStatus(null);

        api.get("/api/policy")
            .then((response) => {
                if (cancelled) return;
                const value = response.data?.test_coverage_min;
                if (typeof value === "number") {
                    setPolicyCoverage(String(value));
                }
            })
            .catch(() => {
                if (cancelled) return;
                setPolicyError("Failed to load org policy.");
            })
            .finally(() => {
                if (cancelled) return;
                setPolicyLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [activeTab]);

    useEffect(() => {
        if (activeTab !== "policies" && activeTab !== "connectors") return;
        void loadScanStatus();
    }, [activeTab, policyUserId]);

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

    const hasConnectedConnector = connectors.some((c) => c.connected);

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

    const formatScanTimestamp = (value?: string) => {
        if (!value) return "Never";
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return value;
        return parsed.toLocaleString();
    };

    const runOrgScan = async (sourceLabel: string) => {
        setScanError(null);
        setScanNotice(null);

        if (!scanStatus?.consent) {
            setScanError("Enable repo scanning before syncing connectors.");
            return;
        }

        const effectiveUserId = policyUserId.trim() || USER_ID;
        setScanLoading(true);
        try {
            await api.post(
                "/api/org/scan/run",
                {},
                {
                    params: {
                        include_secrets: scanAllowSecrets,
                        workspace_root: workspaceRoot || undefined,
                    },
                    headers: { "X-User-Id": effectiveUserId },
                }
            );
            setScanNotice(`${sourceLabel} started. I will update when it completes.`);
            setTimeout(() => {
                void loadScanStatus();
            }, 3000);
        } catch (err: any) {
            const status = err?.response?.status;
            if (status === 403) {
                setScanError("Consent required before scanning. Enable scans in Org policies.");
            } else if (status === 409) {
                setScanError("Scanning is paused. Resume scans to run a sync.");
            } else {
                setScanError("Failed to start scan. Try again.");
            }
        } finally {
            setScanLoading(false);
        }
    };

    const handleScanToggle = async (nextEnabled: boolean) => {
        setScanError(null);
        setScanNotice(null);
        const effectiveUserId = policyUserId.trim() || USER_ID;
        setScanLoading(true);
        try {
            if (nextEnabled) {
                await api.post(
                    "/api/org/scan/consent",
                    {},
                    {
                        params: { allow_secrets: scanAllowSecrets },
                        headers: { "X-User-Id": effectiveUserId },
                    }
                );
                setScanNotice("Repo scanning enabled.");
            } else {
                await api.post("/api/org/scan/revoke", {}, {
                    headers: { "X-User-Id": effectiveUserId },
                });
                setScanNotice("Repo scanning disabled.");
            }
            await loadScanStatus();
        } catch {
            setScanError("Failed to update scan settings.");
        } finally {
            setScanLoading(false);
        }
    };

    const handleAllowSecretsToggle = (nextValue: boolean) => {
        setScanAllowSecrets(nextValue);
        setScanNotice("Secrets setting updated. Re-save scan consent to apply.");
    };

    const handleRunScan = async () => {
        await runOrgScan("Repo scan");
    };

    const handleSyncConnector = async (id: string) => {
        setConnectorSyncing(id);
        await runOrgScan("Connector sync");
        setConnectorSyncing(null);
    };

    const handleSyncAllConnectors = async () => {
        setSyncAllLoading(true);
        try {
            await runOrgScan("Connector sync");
        } finally {
            setSyncAllLoading(false);
        }
    };

    const handlePolicySave = async () => {
        setPolicyError(null);
        setPolicyStatus(null);

        const userId = policyUserId.trim();
        if (!userId) {
            setPolicyError("User id is required to save policies.");
            return;
        }

        if (!policyCoverage.trim()) {
            setPolicyError("Coverage is required.");
            return;
        }

        const coverageValue = Number(policyCoverage);
        if (!Number.isFinite(coverageValue) || coverageValue < 0 || coverageValue > 100) {
            setPolicyError("Coverage must be a number between 0 and 100.");
            return;
        }

        setPolicySaving(true);
        try {
            await api.post(
                "/api/policy",
                { test_coverage_min: Math.round(coverageValue) },
                { headers: { "X-User-Id": userId } }
            );
            setPolicyCoverage(String(Math.round(coverageValue)));
            setPolicyStatus("Policy saved.");
        } catch (err) {
            const status = (err as { response?: { status?: number } })?.response?.status;
            if (status === 403) {
                setPolicyError("Admin or maintainer role required to update policies.");
            } else {
                setPolicyError("Failed to save org policy.");
            }
        } finally {
            setPolicySaving(false);
        }
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
                    <div className="navi-connector-toolbar">
                        <button
                            type="button"
                            className="navi-connector-sync-all-btn"
                            onClick={handleSyncAllConnectors}
                            disabled={!hasConnectedConnector || scanLoading || syncAllLoading}
                        >
                            {syncAllLoading ? "Syncing..." : "Sync all connectors"}
                        </button>
                    </div>
                    {scanError && (
                        <div className="navi-connector-sync-error">{scanError}</div>
                    )}
                    {scanNotice && (
                        <div className="navi-connector-sync-status">{scanNotice}</div>
                    )}
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

                                <button
                                    type="button"
                                    className="navi-connector-sync-btn"
                                    disabled={!c.connected || scanLoading || syncAllLoading}
                                    onClick={() => handleSyncConnector(c.id)}
                                >
                                    {connectorSyncing === c.id ? "Syncing..." : "Sync now"}
                                </button>
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
                        <h3 className="navi-policies-title">Test coverage policy</h3>
                        <p className="navi-policies-text">
                            Set the minimum coverage target that Navi enforces during
                            coverage checks.
                        </p>
                        <div className="navi-policies-grid">
                            <div className="navi-policy-field">
                                <label
                                    className="navi-policy-label"
                                    htmlFor="navi-policy-coverage"
                                >
                                    Coverage minimum (%)
                                </label>
                                <input
                                    id="navi-policy-coverage"
                                    className="navi-policy-input"
                                    type="number"
                                    min={0}
                                    max={100}
                                    value={policyCoverage}
                                    onChange={(event) => {
                                        setPolicyCoverage(event.target.value);
                                        setPolicyStatus(null);
                                    }}
                                />
                                <span className="navi-policy-hint">
                                    Used when you ask for a coverage check in chat.
                                </span>
                            </div>
                            <div className="navi-policy-field">
                                <label className="navi-policy-label" htmlFor="navi-policy-user">
                                    User id (for saving policies)
                                </label>
                                <input
                                    id="navi-policy-user"
                                    className="navi-policy-input"
                                    type="text"
                                    value={policyUserId}
                                    onChange={(event) => {
                                        setPolicyUserId(event.target.value);
                                        setPolicyStatus(null);
                                    }}
                                />
                                <span className="navi-policy-hint">
                                    Must be an org admin or maintainer.
                                </span>
                            </div>
                        </div>
                        <div className="navi-policy-actions">
                            <span className="navi-policy-org">Org: {ORG}</span>
                            <button
                                type="button"
                                className="navi-policy-save-btn"
                                onClick={handlePolicySave}
                                disabled={policyLoading || policySaving}
                            >
                                {policySaving ? "Saving..." : "Save policy"}
                            </button>
                        </div>
                        {policyError && <p className="navi-policy-error">{policyError}</p>}
                        {policyStatus && <p className="navi-policy-status">{policyStatus}</p>}
                    </div>

                    <div className="navi-policies-card">
                        <h3 className="navi-policies-title">Repo + connector scans</h3>
                        <p className="navi-policies-text">
                            Keep NAVI context fresh by scanning the repo and syncing
                            connected systems (Jira, Confluence, Slack, Teams, Zoom).
                        </p>
                        <div className="navi-policies-grid">
                            <label className="navi-policy-toggle">
                                <input
                                    type="checkbox"
                                    checked={Boolean(scanStatus?.consent)}
                                    onChange={(event) => handleScanToggle(event.target.checked)}
                                    disabled={scanLoading}
                                />
                                <span>Enable scheduled scans (every 24h)</span>
                            </label>
                            <label className="navi-policy-toggle">
                                <input
                                    type="checkbox"
                                    checked={scanAllowSecrets}
                                    onChange={(event) => handleAllowSecretsToggle(event.target.checked)}
                                    disabled={!scanStatus?.consent || scanLoading}
                                />
                                <span>Allow secrets paths in scans</span>
                            </label>
                        </div>
                        <div className="navi-policy-actions">
                            <span className="navi-policy-org">
                                Last scan: {formatScanTimestamp(scanStatus?.last_scan_at)}
                            </span>
                            <button
                                type="button"
                                className="navi-policy-save-btn"
                                onClick={handleRunScan}
                                disabled={scanLoading}
                            >
                                {scanLoading ? "Running..." : "Run scan now"}
                            </button>
                        </div>
                        <div className="navi-policy-meta">
                            <span>State: {scanStatus?.state || "unknown"}</span>
                            <span>
                                {scanStatus?.paused_at ? "Paused" : "Active"}
                            </span>
                        </div>
                        {scanError && <p className="navi-policy-error">{scanError}</p>}
                        {scanNotice && <p className="navi-policy-status">{scanNotice}</p>}
                        <p className="navi-policy-hint">
                            Schedule interval is controlled in VS Code settings (
                            <code>aep.navi.autoScanIntervalHours</code>).
                        </p>
                    </div>

                    <div className="navi-policies-card">
                        <h3 className="navi-policies-title">Autonomy policies (coming soon)</h3>
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
