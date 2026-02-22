/**
 * Auth validation utilities
 */

/**
 * Validate returnTo parameter to prevent open redirect attacks.
 * Only allows same-origin paths starting with a single "/".
 * Rejects protocol-relative URLs like "//evil.com".
 */
export function validateReturnTo(returnTo: string | null, defaultPath: string = "/app"): string {
  if (!returnTo) return defaultPath;

  // Must start with "/" but NOT "//" (reject protocol-relative URLs)
  if (!returnTo.startsWith("/") || returnTo.startsWith("//")) {
    return defaultPath;
  }

  // Additional safety: ensure it's a valid path
  try {
    new URL(returnTo, "http://localhost");
    return returnTo;
  } catch {
    return defaultPath;
  }
}
