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

/**
 * Check if the current user has admin role based on JWT claims.
 *
 * ⚠️ WARNING: This is for UI hints only (show/hide admin features).
 * DO NOT use for authorization - the JWT is decoded client-side without
 * signature verification and can be trivially spoofed by editing localStorage.
 * All admin API access MUST be enforced server-side.
 */
export const isAdminUser = (): boolean => {
  const token = getAuthToken();
  if (!token) return false;

  const parts = token.split(".");
  if (parts.length !== 3) return false;

  try {
    // Properly decode base64url by replacing URL-safe chars and adding padding
    let payloadB64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    // Add padding if needed
    while (payloadB64.length % 4 !== 0) payloadB64 += "=";

    const payload = JSON.parse(atob(payloadB64));
    return payload.role === "admin" || (Array.isArray(payload.roles) && payload.roles.includes("admin"));
  } catch {
    return false;
  }
};

