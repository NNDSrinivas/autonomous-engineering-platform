const AUTH_TOKEN_KEY = "aep.navi.authToken.v1";

export type AuthProfile = {
  sub?: string;
  email?: string;
  name?: string;
  org?: string;
};

/**
 * Decode a base64url-encoded string (RFC 4648 §5) to UTF-8.
 * Replaces URL-safe chars, adds padding, and properly handles Unicode.
 */
function decodeBase64Url(base64url: string): string {
  // Replace URL-safe chars with standard base64
  let base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  // Add padding if needed (base64 strings must be multiples of 4)
  while (base64.length % 4 !== 0) {
    base64 += "=";
  }
  // atob returns a binary string; decode as UTF-8 to handle Unicode correctly
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return new TextDecoder("utf-8").decode(bytes);
}

/**
 * Parse a JWT payload without verification.
 * Returns the decoded payload object or null if invalid.
 */
function parseJwtPayload(token: string): Record<string, any> | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    return JSON.parse(decodeBase64Url(parts[1]));
  } catch {
    return null;
  }
}

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
  const payload = parseJwtPayload(token);
  if (!payload) return null;
  return {
    sub: payload.sub,
    email: payload.email,
    name: payload.name,
    org: payload.org || payload.org_id,
  };
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

  const payload = parseJwtPayload(token);
  if (!payload) return false;

  return (
    payload.role === "admin" || (Array.isArray(payload.roles) && payload.roles.includes("admin"))
  );
};

