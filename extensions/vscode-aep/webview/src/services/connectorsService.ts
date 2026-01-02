export type ConnectorStatus = "connected" | "disconnected" | "error";

export interface ConnectorStatusItem {
  id: string;
  name: string;
  category?: string;
  status: ConnectorStatus;
  error?: string | null;
}

export interface ConnectorStatusResponse {
  items: ConnectorStatusItem[];
  offline?: boolean;
}

export interface OAuthAppConfigResponse {
  ok: boolean;
  provider: string;
  configured: boolean;
  client_id?: string;
  scopes?: string;
  tenant_id?: string;
  account_id?: string;
  extra?: Record<string, unknown> | null;
}

export interface OAuthAppConfigRequest {
  provider: string;
  client_id: string;
  client_secret?: string;
  scopes?: string;
  tenant_id?: string;
  account_id?: string;
  extra?: Record<string, unknown> | null;
}

export interface OrgUiConfigResponse {
  ok: boolean;
  base_url?: string | null;
  allowed_domains?: string[];
  redirect_path?: string | null;
}

export interface OrgUiConfigRequest {
  base_url?: string | null;
  allowed_domains?: string[];
  redirect_path?: string | null;
}

export interface JiraConnectPayload {
  base_url: string;
  email: string;
  api_token: string;
}

const FALLBACK_BACKEND_BASE_URL = "http://127.0.0.1:8787";

type RuntimeConfig = {
  backendBaseUrl?: string;
  orgId?: string;
  userId?: string;
  authToken?: string;
};

function getRuntimeConfig(): RuntimeConfig {
  if (typeof window === "undefined") {
    return {};
  }
  const config = (window as any).__AEP_CONFIG__ || {};
  return {
    backendBaseUrl: config.backendBaseUrl,
    orgId: config.orgId,
    userId: config.userId,
    authToken: config.authToken
  };
}

function getBackendBaseUrl(): string {
  return getRuntimeConfig().backendBaseUrl || FALLBACK_BACKEND_BASE_URL;
}

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const { orgId, userId, authToken } = getRuntimeConfig();
  if (orgId) {
    headers["X-Org-Id"] = orgId;
  }
  if (userId) {
    headers["X-User-Id"] = userId;
  }
  if (authToken) {
    headers.Authorization = authToken.startsWith("Bearer ") ? authToken : `Bearer ${authToken}`;
  }
  return headers;
}

export async function fetchConnectorStatus(): Promise<ConnectorStatusResponse> {
  const res = await fetch(`${getBackendBaseUrl()}/api/connectors/status`, {
    method: "GET",
    headers: buildHeaders(),
  });

  if (!res.ok) {
    throw new Error(`Status request failed: ${res.status}`);
  }

  return res.json();
}

export async function startOAuth(
  provider: string,
  installScope: "org" | "user",
  uiOrigin?: string,
): Promise<string> {
  const params = new URLSearchParams({ install: installScope });
  if (uiOrigin) {
    params.set("ui_origin", uiOrigin);
  }
  const res = await fetch(
    `${getBackendBaseUrl()}/api/connectors/${provider}/oauth/start?${params.toString()}`,
    {
      method: "GET",
      headers: buildHeaders(),
    },
  );

  if (!res.ok) {
    throw new Error(`OAuth start failed: ${res.status}`);
  }

  const payload = await res.json();
  const authUrl = payload.auth_url || payload.url;
  if (!authUrl) {
    throw new Error("OAuth start response missing auth_url");
  }

  return authUrl;
}

export async function fetchOAuthConfig(
  provider: string,
): Promise<OAuthAppConfigResponse> {
  const res = await fetch(`${getBackendBaseUrl()}/api/connectors/oauth/config/${provider}`, {
    method: "GET",
    headers: buildHeaders(),
  });

  if (!res.ok) {
    throw new Error(`OAuth config request failed: ${res.status}`);
  }

  return res.json();
}

export async function saveOAuthConfig(
  payload: OAuthAppConfigRequest,
): Promise<OAuthAppConfigResponse> {
  const res = await fetch(`${getBackendBaseUrl()}/api/connectors/oauth/config`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `OAuth config save failed: ${res.status}`);
  }

  return res.json();
}

export async function fetchOrgUiConfig(): Promise<OrgUiConfigResponse> {
  const res = await fetch(`${getBackendBaseUrl()}/api/connectors/ui/config`, {
    method: "GET",
    headers: buildHeaders(),
  });

  if (!res.ok) {
    throw new Error(`Org UI config request failed: ${res.status}`);
  }

  return res.json();
}

export async function saveOrgUiConfig(
  payload: OrgUiConfigRequest,
): Promise<OrgUiConfigResponse> {
  const res = await fetch(`${getBackendBaseUrl()}/api/connectors/ui/config`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Org UI config save failed: ${res.status}`);
  }

  return res.json();
}

export async function connectJira(payload: JiraConnectPayload): Promise<boolean> {
  const res = await fetch(`${getBackendBaseUrl()}/api/connectors/jira/connect`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Jira connect failed: ${res.status}`);
  }

  const data = await res.json();
  return Boolean(data.ok);
}
