/**
 * Auth validation utilities
 */

/**
 * Validate returnTo parameter to prevent open redirect attacks.
 * Only allows same-origin paths starting with a single "/".
 * Rejects protocol-relative URLs, encoded bypasses, and backslash tricks.
 */
export function validateReturnTo(returnTo: string | null, defaultPath: string = "/app"): string {
  if (!returnTo) return defaultPath;

  // Must start with "/" but NOT "//" (reject protocol-relative URLs)
  if (!returnTo.startsWith("/") || returnTo.startsWith("//")) {
    return defaultPath;
  }

  // Reject encoded characters that could bypass checks (e.g., "/%2F/evil.com")
  // Decode and check if it still starts with single "/"
  try {
    const decoded = decodeURIComponent(returnTo);
    if (!decoded.startsWith("/") || decoded.startsWith("//")) {
      return defaultPath;
    }
  } catch {
    // Invalid URI encoding
    return defaultPath;
  }

  // Reject backslash-based bypasses (e.g., "/\evil.com")
  if (returnTo.includes("\\")) {
    return defaultPath;
  }

  // Additional safety: ensure it's a valid path when parsed as URL
  try {
    const url = new URL(returnTo, "http://localhost");

    // Reject URLs with query params or hash fragments (security: prevent parameter injection)
    if (url.search || url.hash) {
      return defaultPath;
    }

    // Verify the pathname matches the input (prevents clever bypasses)
    if (url.pathname !== returnTo) {
      return defaultPath;
    }

    return returnTo;
  } catch {
    return defaultPath;
  }
}
