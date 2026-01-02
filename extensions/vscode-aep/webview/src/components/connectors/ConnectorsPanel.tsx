import React, { useEffect, useMemo, useState } from "react";
import { postMessage } from "../../utils/vscodeApi";
import {
  ConnectorStatus,
  ConnectorStatusResponse,
  OAuthAppConfigResponse,
  OrgUiConfigResponse,
  connectJira,
  fetchConnectorStatus,
  fetchOrgUiConfig,
  fetchOAuthConfig,
  saveOrgUiConfig,
  saveOAuthConfig,
  startOAuth,
} from "../../services/connectorsService";

type ConnectorAuth = "oauth" | "token" | "coming_soon";

interface ConnectorDefinition {
  id: string;
  name: string;
  category: string;
  description: string;
  auth: ConnectorAuth;
  accent: string;
  capabilities: string[];
  featured?: boolean;
}

interface OAuthConfigFormState {
  clientId: string;
  clientSecret: string;
  scopes: string;
  tenantId: string;
  accountId: string;
}

interface OrgUiConfigFormState {
  baseUrl: string;
  allowedDomains: string;
  redirectPath: string;
}

interface ConnectorsPanelProps {
  open: boolean;
  onClose: () => void;
}

const CONNECTORS: ConnectorDefinition[] = [
  {
    id: "slack",
    name: "Slack",
    category: "Chat",
    description: "Channels, DMs, files, and mentions with real-time sync.",
    auth: "oauth",
    accent: "#36C5F0",
    capabilities: ["messages", "files", "mentions"],
    featured: true,
  },
  {
    id: "github",
    name: "GitHub",
    category: "Code",
    description: "PRs, issues, checks, and write actions gated by governance.",
    auth: "oauth",
    accent: "#0EA5E9",
    capabilities: ["prs", "issues", "webhooks"],
    featured: true,
  },
  {
    id: "jira",
    name: "Jira",
    category: "Work",
    description: "Live issue context, transitions, and ownership signals.",
    auth: "token",
    accent: "#2684FF",
    capabilities: ["issues", "status", "triage"],
  },
  {
    id: "confluence",
    name: "Confluence",
    category: "Docs",
    description: "Spaces, pages, and knowledge indexing for context.",
    auth: "oauth",
    accent: "#00A3BF",
    capabilities: ["spaces", "pages", "webhooks"],
  },
  {
    id: "teams",
    name: "Microsoft Teams",
    category: "Chat",
    description: "Channels, mentions, and collaboration threads.",
    auth: "oauth",
    accent: "#6264A7",
    capabilities: ["channels", "mentions", "sync"],
  },
  {
    id: "zoom",
    name: "Zoom",
    category: "Meetings",
    description: "Meeting summaries, actions, and transcript ingestion.",
    auth: "oauth",
    accent: "#2D8CFF",
    capabilities: ["meetings", "transcripts", "actions"],
  },
  {
    id: "meet",
    name: "Google Meet",
    category: "Meetings",
    description: "Calendar-aware meetings with transcript hydration.",
    auth: "oauth",
    accent: "#34A853",
    capabilities: ["calendar", "transcripts", "signals"],
  },
  {
    id: "gitlab",
    name: "GitLab",
    category: "Code",
    description: "Repo signals and MR workflows (planned).",
    auth: "coming_soon",
    accent: "#FC6D26",
    capabilities: ["mrs", "issues"],
  },
  {
    id: "jenkins",
    name: "Jenkins",
    category: "CI",
    description: "Build telemetry and CI coverage (planned).",
    auth: "coming_soon",
    accent: "#D33833",
    capabilities: ["builds", "logs"],
  },
];

const statusLabels: Record<ConnectorStatus, string> = {
  connected: "Connected",
  disconnected: "Not connected",
  error: "Needs attention",
};

function openExternal(url: string) {
  if (!url) return;
  postMessage({ type: "openExternal", url });
  if (typeof window !== "undefined" && !window.acquireVsCodeApi) {
    window.open(url, "_blank", "noopener");
  }
}

function statusClass(status: ConnectorStatus) {
  switch (status) {
    case "connected":
      return "border-emerald-400/40 text-emerald-200 bg-emerald-500/10";
    case "error":
      return "border-rose-400/40 text-rose-200 bg-rose-500/10";
    default:
      return "border-slate-500/40 text-slate-200 bg-slate-500/10";
  }
}

function ConnectorIcon({ id }: { id: string }) {
  switch (id) {
    case "slack":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <path d="M6 13.5a2 2 0 1 1-2-2h2v2z" fill="currentColor" />
          <path d="M7 13.5a2 2 0 1 1 4 0v6a2 2 0 1 1-4 0v-6z" fill="currentColor" />
          <path d="M10.5 6a2 2 0 1 1 2-2v2h-2z" fill="currentColor" />
          <path d="M10.5 7a2 2 0 1 1 0 4h-6a2 2 0 1 1 0-4h6z" fill="currentColor" />
          <path d="M18 10.5a2 2 0 1 1 2 2h-2v-2z" fill="currentColor" />
          <path d="M17 10.5a2 2 0 1 1-4 0v-6a2 2 0 1 1 4 0v6z" fill="currentColor" />
          <path d="M13.5 18a2 2 0 1 1-2 2v-2h2z" fill="currentColor" />
          <path d="M13.5 17a2 2 0 1 1 0-4h6a2 2 0 1 1 0 4h-6z" fill="currentColor" />
        </svg>
      );
    case "github":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2.8a9.2 9.2 0 0 0-2.9 17.9c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.4-1.1-1-1.4-1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.4 1.1 3 .9.1-.6.4-1.1.7-1.3-2.2-.3-4.5-1.1-4.5-5a3.9 3.9 0 0 1 1-2.7 3.6 3.6 0 0 1 .1-2.6s.9-.3 2.8 1a9.6 9.6 0 0 1 5.1 0c1.9-1.3 2.8-1 2.8-1 .6 1.4.2 2.4.1 2.6a3.9 3.9 0 0 1 1 2.7c0 3.9-2.3 4.7-4.5 5 .4.3.8 1 .8 2.1v3.1c0 .3.2.6.7.5A9.2 9.2 0 0 0 12 2.8z"
            fill="currentColor"
          />
        </svg>
      );
    case "jira":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <path d="M4.2 4.2h7.2c0 4-3.2 7.2-7.2 7.2V4.2z" fill="currentColor" />
          <path d="M12.6 4.2h7.2c0 4-3.2 7.2-7.2 7.2V4.2z" fill="currentColor" />
          <path d="M8.4 12.6h7.2c0 4-3.2 7.2-7.2 7.2v-7.2z" fill="currentColor" />
        </svg>
      );
    case "confluence":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <path
            d="M7.2 7.2c2.2-1.7 5.4-1.2 7.1 1l2.5 3.3c.4.5.3 1.3-.3 1.7l-1.3.9c-.6.4-1.4.2-1.8-.3l-2.2-2.9c-.7-.9-2-1.1-2.9-.4l-3.6 2.7c-.6.4-1.4.3-1.9-.2l-.9-1.1c-.4-.6-.3-1.4.3-1.9L7.2 7.2z"
            fill="currentColor"
          />
          <path
            d="M16.8 16.8c-2.2 1.7-5.4 1.2-7.1-1l-2.5-3.3c-.4-.5-.3-1.3.3-1.7l1.3-.9c.6-.4 1.4-.2 1.8.3l2.2 2.9c.7.9 2 1.1 2.9.4l3.6-2.7c.6-.4 1.4-.3 1.9.2l.9 1.1c.4.6.3 1.4-.3 1.9l-4.3 3.8z"
            fill="currentColor"
          />
        </svg>
      );
    case "teams":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <path d="M3.8 8.5h9.4v9.4H3.8z" fill="currentColor" />
          <path d="M14.5 7.2h5.7v5.7h-5.7z" fill="currentColor" />
          <path d="M10 11h3.5v7H10z" fill="currentColor" />
        </svg>
      );
    case "zoom":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="7" width="12" height="10" rx="2" fill="currentColor" />
          <path d="M16 9l5 3v0l-5 3V9z" fill="currentColor" />
        </svg>
      );
    case "meet":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="7" width="11" height="10" rx="2" fill="currentColor" />
          <path d="M15 9l6-3v12l-6-3V9z" fill="currentColor" />
        </svg>
      );
    default:
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="6" stroke="currentColor" strokeWidth="2" />
        </svg>
      );
  }
}

export function ConnectorsPanel({ open, onClose }: ConnectorsPanelProps) {
  const [status, setStatus] = useState<Record<string, ConnectorStatus>>({});
  const [statusError, setStatusError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [filter, setFilter] = useState<"all" | "connected" | "missing">("all");
  const [installScope, setInstallScope] = useState<"org" | "user">("org");
  const [search, setSearch] = useState("");
  const [busyConnector, setBusyConnector] = useState<string | null>(null);
  const [oauthConfig, setOauthConfig] = useState<Record<string, OAuthAppConfigResponse>>({});
  const [orgUiConfig, setOrgUiConfig] = useState<OrgUiConfigResponse | null>(null);
  const [orgUiConfigOpen, setOrgUiConfigOpen] = useState(false);
  const [orgUiConfigBusy, setOrgUiConfigBusy] = useState(false);
  const [orgUiConfigError, setOrgUiConfigError] = useState<string | null>(null);
  const [orgUiConfigForm, setOrgUiConfigForm] = useState<OrgUiConfigFormState>({
    baseUrl: "",
    allowedDomains: "",
    redirectPath: "/settings/connectors",
  });
  const [configTarget, setConfigTarget] = useState<ConnectorDefinition | null>(null);
  const [configBusy, setConfigBusy] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configForm, setConfigForm] = useState<OAuthConfigFormState>({
    clientId: "",
    clientSecret: "",
    scopes: "",
    tenantId: "",
    accountId: "",
  });
  const [jiraFormOpen, setJiraFormOpen] = useState(false);
  const [jiraForm, setJiraForm] = useState({
    baseUrl: "",
    email: "",
    apiToken: "",
  });

  const loadOAuthConfigs = async () => {
    const oauthConnectors = CONNECTORS.filter((connector) => connector.auth === "oauth");
    if (!oauthConnectors.length) return;
    const results = await Promise.allSettled(
      oauthConnectors.map((connector) => fetchOAuthConfig(connector.id)),
    );
    const nextConfig: Record<string, OAuthAppConfigResponse> = {};
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        nextConfig[oauthConnectors[index].id] = result.value;
      }
    });
    if (Object.keys(nextConfig).length) {
      setOauthConfig((prev) => ({ ...prev, ...nextConfig }));
    }
  };

  const refreshStatus = async () => {
    setStatusError(null);
    try {
      const data: ConnectorStatusResponse = await fetchConnectorStatus();
      const mapped = data.items.reduce<Record<string, ConnectorStatus>>((acc, item) => {
        acc[item.id] = item.status;
        return acc;
      }, {});
      setStatus(mapped);
      setOffline(Boolean(data.offline));
    } catch (err) {
      setStatusError("Unable to reach the connectors service.");
      setOffline(true);
    }
    try {
      await loadOAuthConfigs();
    } catch (err) {
    }
    try {
      const uiConfig = await fetchOrgUiConfig();
      setOrgUiConfig(uiConfig);
      setOrgUiConfigForm({
        baseUrl: uiConfig.base_url || "",
        allowedDomains: (uiConfig.allowed_domains || []).join(", "),
        redirectPath: uiConfig.redirect_path || "/settings/connectors",
      });
    } catch (err) {
    }
  };

  useEffect(() => {
    if (!open) return;
    refreshStatus();
  }, [open]);

  const connectedCount = useMemo(
    () => CONNECTORS.filter((connector) => status[connector.id] === "connected").length,
    [status],
  );

  const filteredConnectors = useMemo(() => {
    return CONNECTORS.filter((connector) => {
      const statusValue = status[connector.id] || "disconnected";
      if (filter === "connected" && statusValue !== "connected") {
        return false;
      }
      if (filter === "missing" && statusValue === "connected") {
        return false;
      }
      if (search.trim()) {
        const needle = search.trim().toLowerCase();
        return (
          connector.name.toLowerCase().includes(needle) ||
          connector.category.toLowerCase().includes(needle)
        );
      }
      return true;
    });
  }, [filter, search, status]);

  const handleOAuthConnect = async (connectorId: string) => {
    const appConfig = oauthConfig[connectorId];
    if (appConfig && !appConfig.configured) {
      setStatusError(`${connectorId} OAuth app is not configured yet.`);
      return;
    }
    setBusyConnector(connectorId);
    try {
      const uiOrigin = orgUiConfig?.base_url || undefined;
      const url = await startOAuth(connectorId, installScope, uiOrigin || undefined);
      openExternal(url);
    } catch (err) {
      setStatusError("OAuth start failed. Check backend OAuth configuration.");
    } finally {
      setBusyConnector(null);
    }
  };

  const handleJiraConnect = async () => {
    setBusyConnector("jira");
    if (!jiraForm.baseUrl.trim() || !jiraForm.email.trim() || !jiraForm.apiToken.trim()) {
      setStatusError("Jira requires base URL, email, and API token.");
      setBusyConnector(null);
      return;
    }
    try {
      await connectJira({
        base_url: jiraForm.baseUrl.trim(),
        email: jiraForm.email.trim(),
        api_token: jiraForm.apiToken.trim(),
      });
      setJiraFormOpen(false);
      setJiraForm({ baseUrl: "", email: "", apiToken: "" });
      await refreshStatus();
    } catch (err) {
      setStatusError("Jira connection failed. Double-check the token and base URL.");
    } finally {
      setBusyConnector(null);
    }
  };

  const openConfigModal = async (connector: ConnectorDefinition) => {
    setConfigTarget(connector);
    setConfigError(null);
    setConfigBusy(false);

    let config = oauthConfig[connector.id];
    if (!config) {
      try {
        const fetched = await fetchOAuthConfig(connector.id);
        config = fetched;
        setOauthConfig((prev) => ({ ...prev, [connector.id]: fetched }));
      } catch (err) {
        setConfigError("Unable to load OAuth app configuration.");
      }
    }

    setConfigForm({
      clientId: config?.client_id || "",
      clientSecret: "",
      scopes: config?.scopes || "",
      tenantId: config?.tenant_id || "",
      accountId: config?.account_id || "",
    });
  };

  const closeConfigModal = () => {
    setConfigTarget(null);
    setConfigError(null);
    setConfigForm({
      clientId: "",
      clientSecret: "",
      scopes: "",
      tenantId: "",
      accountId: "",
    });
  };

  const handleConfigSave = async () => {
    if (!configTarget) return;
    if (!configForm.clientId.trim()) {
      setConfigError("Client ID is required.");
      return;
    }
    setConfigBusy(true);
    setConfigError(null);
    try {
      const payload = {
        provider: configTarget.id,
        client_id: configForm.clientId.trim(),
        client_secret: configForm.clientSecret.trim() || undefined,
        scopes: configForm.scopes.trim() || undefined,
        tenant_id: configForm.tenantId.trim() || undefined,
        account_id: configForm.accountId.trim() || undefined,
      };
      const saved = await saveOAuthConfig(payload);
      setOauthConfig((prev) => ({ ...prev, [configTarget.id]: saved }));
      closeConfigModal();
    } catch (err) {
      const message = err instanceof Error ? err.message : "OAuth app save failed.";
      setConfigError(message);
    } finally {
      setConfigBusy(false);
    }
  };

  const openOrgUiConfigModal = () => {
    setOrgUiConfigError(null);
    setOrgUiConfigForm({
      baseUrl: orgUiConfig?.base_url || "",
      allowedDomains: (orgUiConfig?.allowed_domains || []).join(", "),
      redirectPath: orgUiConfig?.redirect_path || "/settings/connectors",
    });
    setOrgUiConfigOpen(true);
  };

  const closeOrgUiConfigModal = () => {
    setOrgUiConfigOpen(false);
    setOrgUiConfigError(null);
  };

  const handleOrgUiConfigSave = async () => {
    setOrgUiConfigBusy(true);
    setOrgUiConfigError(null);
    const domains = orgUiConfigForm.allowedDomains
      .split(/[,\n]/)
      .map((value) => value.trim())
      .filter(Boolean);
    try {
      const saved = await saveOrgUiConfig({
        base_url: orgUiConfigForm.baseUrl.trim() || null,
        allowed_domains: domains,
        redirect_path: orgUiConfigForm.redirectPath.trim() || null,
      });
      setOrgUiConfig(saved);
      setOrgUiConfigForm({
        baseUrl: saved.base_url || "",
        allowedDomains: (saved.allowed_domains || []).join(", "),
        redirectPath: saved.redirect_path || "/settings/connectors",
      });
      closeOrgUiConfigModal();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Org UI config save failed.";
      setOrgUiConfigError(message);
    } finally {
      setOrgUiConfigBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(60,120,200,0.25),_transparent_55%),linear-gradient(180deg,rgba(10,12,16,0.85),rgba(10,12,16,0.95))]"
        onClick={onClose}
      />
      <div
        className="connector-panel-enter relative mx-auto w-[min(92vw,980px)] max-h-[90vh] overflow-hidden rounded-2xl border border-[var(--vscode-panel-border)] bg-[var(--vscode-editor-background)] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="absolute -left-16 top-20 h-40 w-40 rounded-full bg-sky-500/20 blur-3xl" />
        <div className="absolute -right-8 top-12 h-32 w-32 rounded-full bg-emerald-400/20 blur-3xl" />

        <div className="flex items-center justify-between border-b border-[var(--vscode-panel-border)] px-5 py-4">
          <div>
            <div className="text-base font-semibold text-[var(--vscode-foreground)]">
              Connectors
            </div>
            <div className="text-xs text-[var(--vscode-descriptionForeground)]">
              {connectedCount} connected · {CONNECTORS.length} available
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full border border-transparent px-2 py-1 text-xs text-[var(--vscode-descriptionForeground)] hover:border-[var(--vscode-panel-border)] hover:text-[var(--vscode-foreground)]"
          >
            Close
          </button>
        </div>

        <div className="max-h-[calc(90vh-72px)] overflow-y-auto px-5 py-4">
          <div className="grid gap-4 md:grid-cols-[1.2fr_1fr_1fr]">
            <div className="connector-card-enter relative overflow-hidden rounded-xl border border-slate-700/60 bg-slate-900/40 p-4">
              <div className="absolute inset-0 connector-sheen opacity-30" />
              <div className="text-sm font-semibold text-slate-100">
                Wire NAVI into your stack
              </div>
              <div className="mt-2 text-xs text-slate-300">
                Live ingestion, governance-gated write actions, and memory graph
                hydration from your daily tools.
              </div>
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-300">
                <span className="rounded-full border border-slate-600 px-2 py-1">
                  realtime
                </span>
                <span className="rounded-full border border-slate-600 px-2 py-1">
                  secure
                </span>
                <span className="rounded-full border border-slate-600 px-2 py-1">
                  audit
                </span>
              </div>
            </div>

            <div className="connector-card-enter rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
              <div className="text-xs text-slate-300">Install scope</div>
              <div className="mt-2 flex items-center rounded-lg border border-slate-700/60 bg-slate-950/40 p-1 text-xs">
                <button
                  onClick={() => setInstallScope("org")}
                  className={`flex-1 rounded-md px-2 py-1 ${installScope === "org" ? "bg-slate-200 text-slate-900" : "text-slate-300"}`}
                >
                  Org install
                </button>
                <button
                  onClick={() => setInstallScope("user")}
                  className={`flex-1 rounded-md px-2 py-1 ${installScope === "user" ? "bg-slate-200 text-slate-900" : "text-slate-300"}`}
                >
                  Personal
                </button>
              </div>
              <div className="mt-2 text-[11px] text-slate-400">
                Org install is recommended for shared workspaces.
              </div>
            </div>

            <div className="connector-card-enter rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
              <div className="flex items-center justify-between text-xs text-slate-300">
                <span>Status</span>
                <button
                  onClick={refreshStatus}
                  className="rounded-md border border-slate-600 px-2 py-1 text-[11px] text-slate-200 hover:border-slate-400"
                >
                  Refresh
                </button>
              </div>
              <div className="mt-2 text-xs text-slate-400">
                {offline
                  ? "Offline. Check backend connectivity."
                  : "Live status from your backend."}
              </div>
              {statusError ? (
                <div className="mt-2 text-[11px] text-rose-200">{statusError}</div>
              ) : null}
            </div>

            <div className="connector-card-enter rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
              <div className="flex items-center justify-between text-xs text-slate-300">
                <span>Org redirect settings</span>
                <button
                  onClick={openOrgUiConfigModal}
                  className="rounded-md border border-slate-600 px-2 py-1 text-[11px] text-slate-200 hover:border-slate-400"
                >
                  Configure
                </button>
              </div>
              <div className="mt-2 text-xs text-slate-400">
                {orgUiConfig?.base_url
                  ? `Primary UI: ${orgUiConfig.base_url}`
                  : "No primary UI domain configured yet."}
              </div>
              <div className="mt-2 text-[11px] text-slate-400">
                Redirect path: {orgUiConfig?.redirect_path || "/settings/connectors"}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                Allowed domains: {orgUiConfig?.allowed_domains?.length || 0}
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <div className="flex-1 min-w-[180px]">
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search connectors..."
                className="w-full rounded-lg border border-slate-700/70 bg-slate-950/40 px-3 py-2 text-xs text-slate-200 outline-none focus:border-slate-400"
              />
            </div>
            <div className="flex items-center gap-2 text-xs">
              {(["all", "connected", "missing"] as const).map((value) => (
                <button
                  key={value}
                  onClick={() => setFilter(value)}
                  className={`rounded-full border px-3 py-1 ${filter === value ? "border-slate-200 bg-slate-200 text-slate-900" : "border-slate-600 text-slate-300"}`}
                >
                  {value === "all" ? "All" : value === "connected" ? "Connected" : "Missing"}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {filteredConnectors.map((connector, index) => {
              const statusValue = status[connector.id] || "disconnected";
              const isBusy = busyConnector === connector.id;
              const isConnected = statusValue === "connected";
              const isComingSoon = connector.auth === "coming_soon";
              const appConfig = oauthConfig[connector.id];
              const appConfigured = Boolean(appConfig?.configured);
              const appStatusLabel = appConfig
                ? appConfigured
                  ? "App configured"
                  : "App not configured"
                : "App status unknown";
              const appStatusClass = !appConfig
                ? "border-slate-600/60 text-slate-300"
                : appConfigured
                  ? "border-emerald-400/40 text-emerald-200"
                  : "border-amber-400/40 text-amber-200";
              const showJiraForm = connector.id === "jira" && jiraFormOpen;

              return (
                <div
                  key={connector.id}
                  className="connector-card-enter group rounded-xl border border-slate-800/80 bg-slate-950/40 p-4"
                  style={{ animationDelay: `${index * 35}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="connector-float-slow flex h-10 w-10 items-center justify-center rounded-lg"
                        style={{
                          background: `linear-gradient(135deg, ${connector.accent}33, transparent)`,
                          color: connector.accent,
                        }}
                      >
                        <ConnectorIcon id={connector.id} />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-slate-100">
                          {connector.name}
                        </div>
                        <div className="text-xs text-slate-400">
                          {connector.category}
                        </div>
                      </div>
                    </div>
                    <span
                      className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-wide ${statusClass(statusValue)}`}
                    >
                      {statusLabels[statusValue]}
                    </span>
                  </div>

                  <div className="mt-3 text-xs text-slate-300">
                    {connector.description}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide text-slate-400">
                    {connector.capabilities.map((capability) => (
                      <span
                        key={capability}
                        className="rounded-full border border-slate-700 px-2 py-1"
                      >
                        {capability}
                      </span>
                    ))}
                  </div>

                  {connector.id === "jira" ? (
                    <div className="mt-4 space-y-2">
                      <button
                        onClick={() => setJiraFormOpen((prev) => !prev)}
                        className="w-full rounded-lg border border-slate-600/70 px-3 py-2 text-xs text-slate-200 hover:border-slate-400"
                      >
                        {jiraFormOpen ? "Hide Jira credentials" : "Connect with API token"}
                      </button>
                      {showJiraForm ? (
                        <div className="space-y-2 rounded-lg border border-slate-800/70 bg-slate-950/60 p-3 text-xs text-slate-200">
                          <input
                            value={jiraForm.baseUrl}
                            onChange={(event) =>
                              setJiraForm((prev) => ({ ...prev, baseUrl: event.target.value }))
                            }
                            placeholder="https://your-domain.atlassian.net"
                            className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                          />
                          <input
                            value={jiraForm.email}
                            onChange={(event) =>
                              setJiraForm((prev) => ({ ...prev, email: event.target.value }))
                            }
                            placeholder="Email address"
                            className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                          />
                          <input
                            type="password"
                            value={jiraForm.apiToken}
                            onChange={(event) =>
                              setJiraForm((prev) => ({ ...prev, apiToken: event.target.value }))
                            }
                            placeholder="API token"
                            className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                          />
                          <button
                            onClick={handleJiraConnect}
                            disabled={isBusy}
                            className="w-full rounded-md bg-slate-200 px-3 py-2 text-xs font-semibold text-slate-900 disabled:opacity-60"
                          >
                            {isBusy ? "Connecting..." : "Connect Jira"}
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="mt-4 space-y-2">
                      <div className="flex items-center gap-2">
                        {isComingSoon ? (
                          <button
                            disabled
                            className="w-full rounded-lg border border-slate-700/60 px-3 py-2 text-xs text-slate-500"
                          >
                            Coming soon
                          </button>
                        ) : (
                          <button
                            onClick={() => handleOAuthConnect(connector.id)}
                            disabled={isBusy}
                            className="w-full rounded-lg px-3 py-2 text-xs font-semibold text-slate-900 disabled:opacity-60"
                            style={{
                              background: `linear-gradient(135deg, ${connector.accent}, #F1F5F9)`,
                            }}
                          >
                            {isConnected ? "Manage connection" : "Connect"}
                          </button>
                        )}
                      </div>
                      {connector.auth === "oauth" && !isComingSoon ? (
                        <div className="flex items-center justify-between text-[11px] text-slate-400">
                          <span className={`rounded-full border px-2 py-1 ${appStatusClass}`}>
                            {appStatusLabel}
                          </span>
                          <button
                            onClick={() => openConfigModal(connector)}
                            className="rounded-md border border-slate-700/60 px-2 py-1 text-[11px] text-slate-200 hover:border-slate-400"
                          >
                            Configure app
                          </button>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {configTarget ? (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm"
            onClick={closeConfigModal}
          >
            <div
              className="w-[min(90vw,520px)] rounded-xl border border-slate-700/60 bg-slate-950 p-5 text-slate-100 shadow-xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold">
                    Configure {configTarget.name} OAuth app
                  </div>
                  <div className="text-xs text-slate-400">
                    Stored for your org. Client secret is write-only.
                  </div>
                </div>
                <button
                  onClick={closeConfigModal}
                  className="rounded-md border border-slate-700/60 px-2 py-1 text-xs text-slate-300 hover:border-slate-400"
                >
                  Close
                </button>
              </div>

              <div className="mt-4 space-y-2 text-xs">
                <input
                  value={configForm.clientId}
                  onChange={(event) =>
                    setConfigForm((prev) => ({ ...prev, clientId: event.target.value }))
                  }
                  placeholder="Client ID"
                  className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                />
                <input
                  type="password"
                  value={configForm.clientSecret}
                  onChange={(event) =>
                    setConfigForm((prev) => ({ ...prev, clientSecret: event.target.value }))
                  }
                  placeholder="Client secret (leave blank to keep existing)"
                  className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                />
                <input
                  value={configForm.scopes}
                  onChange={(event) =>
                    setConfigForm((prev) => ({ ...prev, scopes: event.target.value }))
                  }
                  placeholder="Scopes override (space-delimited)"
                  className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                />
                {configTarget.id === "teams" ? (
                  <input
                    value={configForm.tenantId}
                    onChange={(event) =>
                      setConfigForm((prev) => ({ ...prev, tenantId: event.target.value }))
                    }
                    placeholder="Tenant ID (optional)"
                    className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                  />
                ) : null}
                {configTarget.id === "zoom" ? (
                  <input
                    value={configForm.accountId}
                    onChange={(event) =>
                      setConfigForm((prev) => ({ ...prev, accountId: event.target.value }))
                    }
                    placeholder="Account ID (optional)"
                    className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                  />
                ) : null}
              </div>

              {configError ? (
                <div className="mt-2 text-[11px] text-rose-200">{configError}</div>
              ) : null}

              <div className="mt-4 flex items-center gap-2">
                <button
                  onClick={handleConfigSave}
                  disabled={configBusy}
                  className="rounded-md bg-slate-200 px-4 py-2 text-xs font-semibold text-slate-900 disabled:opacity-60"
                >
                  {configBusy ? "Saving..." : "Save config"}
                </button>
                <button
                  onClick={closeConfigModal}
                  className="rounded-md border border-slate-700/60 px-4 py-2 text-xs text-slate-200 hover:border-slate-400"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        ) : null}
        {orgUiConfigOpen ? (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm"
            onClick={closeOrgUiConfigModal}
          >
            <div
              className="w-[min(90vw,520px)] rounded-xl border border-slate-700/60 bg-slate-950 p-5 text-slate-100 shadow-xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold">Org UI redirect settings</div>
                  <div className="text-xs text-slate-400">
                    Configure allowed UI domains for OAuth redirects.
                  </div>
                </div>
                <button
                  onClick={closeOrgUiConfigModal}
                  className="rounded-md border border-slate-700/60 px-2 py-1 text-xs text-slate-300 hover:border-slate-400"
                >
                  Close
                </button>
              </div>

              <div className="mt-4 space-y-2 text-xs">
                <input
                  value={orgUiConfigForm.baseUrl}
                  onChange={(event) =>
                    setOrgUiConfigForm((prev) => ({ ...prev, baseUrl: event.target.value }))
                  }
                  placeholder="Primary UI base URL (https://app.example.com)"
                  className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                />
                <textarea
                  value={orgUiConfigForm.allowedDomains}
                  onChange={(event) =>
                    setOrgUiConfigForm((prev) => ({
                      ...prev,
                      allowedDomains: event.target.value,
                    }))
                  }
                  placeholder="Allowed UI domains (comma or newline separated)"
                  rows={3}
                  className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                />
                <input
                  value={orgUiConfigForm.redirectPath}
                  onChange={(event) =>
                    setOrgUiConfigForm((prev) => ({
                      ...prev,
                      redirectPath: event.target.value,
                    }))
                  }
                  placeholder="/settings/connectors"
                  className="w-full rounded-md border border-slate-700 bg-transparent px-3 py-2 text-xs text-slate-100 outline-none focus:border-slate-400"
                />
              </div>

              <div className="mt-2 text-[11px] text-slate-400">
                Use HTTPS for production. HTTP is only allowed for localhost.
              </div>

              {orgUiConfigError ? (
                <div className="mt-2 text-[11px] text-rose-200">{orgUiConfigError}</div>
              ) : null}

              <div className="mt-4 flex items-center gap-2">
                <button
                  onClick={handleOrgUiConfigSave}
                  disabled={orgUiConfigBusy}
                  className="rounded-md bg-slate-200 px-4 py-2 text-xs font-semibold text-slate-900 disabled:opacity-60"
                >
                  {orgUiConfigBusy ? "Saving..." : "Save settings"}
                </button>
                <button
                  onClick={closeOrgUiConfigModal}
                  className="rounded-md border border-slate-700/60 px-4 py-2 text-xs text-slate-200 hover:border-slate-400"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
