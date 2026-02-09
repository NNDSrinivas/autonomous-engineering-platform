const AUTH_TOKEN_KEY = "aep.navi.authToken.v1";

export type AuthProfile = {
  sub?: string;
  email?: string;
  name?: string;
  org?: string;
};

export const getAuthToken = (): string | null => {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setAuthToken = (token: string | null) => {
  if (typeof window === "undefined") return;
  try {
    if (!token) {
      window.localStorage.removeItem(AUTH_TOKEN_KEY);
    } else {
      window.localStorage.setItem(AUTH_TOKEN_KEY, token);
    }
  } catch {
    // ignore storage errors
  }
};

export const decodeAuthToken = (token: string | null): AuthProfile | null => {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return {
      sub: payload.sub,
      email: payload.email,
      name: payload.name,
      org: payload.org || payload.org_id,
    };
  } catch {
    return null;
  }
};

