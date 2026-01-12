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

export const ORG = getRuntimeConfig().orgId || import.meta.env.VITE_ORG_ID || "default";
export const USER_ID = getRuntimeConfig().userId || import.meta.env.VITE_USER_ID || "default_user";
