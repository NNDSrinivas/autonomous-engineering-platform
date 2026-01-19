// Minimal runtime config for webview API calls.

type RuntimeConfig = {
  orgId?: string;
  userId?: string;
};

const getRuntimeConfig = (): RuntimeConfig => {
  if (typeof window === "undefined") {
    return {};
  }
  const config = (window as any).__AEP_CONFIG__ || {};
  return {
    orgId: config.orgId,
    userId: config.userId,
  };
};

export const ORG = getRuntimeConfig().orgId || import.meta.env?.VITE_ORG_ID || "default";
export const USER_ID = getRuntimeConfig().userId || import.meta.env?.VITE_USER_ID || "default_user";

// Simple API client for making HTTP requests
const BASE_URL = import.meta.env?.VITE_API_URL || '';

interface ApiResponse<T> {
  data: T;
  status: number;
}

interface RequestConfig {
  params?: Record<string, unknown>;
  headers?: Record<string, string>;
}

async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  url: string,
  data?: unknown,
  config?: RequestConfig
): Promise<ApiResponse<T>> {
  const fullUrl = new URL(url, BASE_URL || window.location.origin);

  if (config?.params) {
    Object.entries(config.params).forEach(([key, value]) => {
      if (value !== undefined) {
        fullUrl.searchParams.set(key, String(value));
      }
    });
  }

  const response = await fetch(fullUrl.toString(), {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...config?.headers,
    },
    body: data ? JSON.stringify(data) : undefined,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const responseData = await response.json();
  return { data: responseData, status: response.status };
}

export const api = {
  get: <T>(url: string, config?: RequestConfig) => request<T>('GET', url, undefined, config),
  post: <T>(url: string, data?: unknown, config?: RequestConfig) => request<T>('POST', url, data, config),
  put: <T>(url: string, data?: unknown, config?: RequestConfig) => request<T>('PUT', url, data, config),
  delete: <T>(url: string, config?: RequestConfig) => request<T>('DELETE', url, undefined, config),
};

// Core API URL for SSE and other services
export const CORE_API = BASE_URL || '';
