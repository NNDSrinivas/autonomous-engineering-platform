// Webview NAVI API helpers (runtime-config aware).

const FALLBACK_BACKEND_BASE_URL = "http://127.0.0.1:8787";

type RuntimeConfig = {
  backendBaseUrl?: string;
};

function getRuntimeConfig(): RuntimeConfig {
  if (typeof window === "undefined") {
    return {};
  }
  const config = (window as any).__AEP_CONFIG__ || {};
  return {
    backendBaseUrl: config.backendBaseUrl,
  };
}

/**
 * Resolve the backend base URL.
 * Priority:
 * 1) VS Code webview runtime config
 * 2) Same-origin (local dev)
 * 3) Fallback localhost
 */
export function resolveBackendBase(): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const override = getRuntimeConfig().backendBaseUrl;

  const base = override || origin || FALLBACK_BACKEND_BASE_URL;
  const cleaned = base.replace(/\/$/, "");
  return cleaned.replace(/\/api\/navi\/chat$/i, "");
}
