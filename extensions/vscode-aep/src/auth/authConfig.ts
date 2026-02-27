/**
 * Auth0 configuration resolver for environment-aware PKCE authentication.
 *
 * Automatically selects the correct Auth0 Native app based on the backend URL.
 */

export type Environment = 'dev' | 'staging' | 'production';

export interface AuthConfig {
  auth0Domain: string;
  clientId: string;
  audience: string;
  environment: Environment;
}

/**
 * Auth0 Native app client IDs for each environment.
 * These are public client IDs (not secrets) - safe to hardcode.
 */
const AUTH0_CLIENT_IDS: Record<Environment, string> = {
  dev: 'G5PtcWXaYKJ8JD2ktA9j40wwVnBuwOzu',
  staging: 'ZtGrpbrjy6LuHHz1yeTiWwfb8FKZc5QT',
  production: 'VieiheBGMQu3rSq4fyqtjCZj3H9Q0Alq',
};

/**
 * API audiences for each environment.
 */
const AUTH0_AUDIENCES: Record<Environment, string> = {
  dev: 'https://api-dev.navralabs.com',
  staging: 'https://api-staging.navralabs.com',
  production: 'https://api.navralabs.com',
};

/**
 * Auth0 issuer (custom domain) - same for all environments.
 */
const AUTH0_ISSUER = 'https://auth.navralabs.com';

/**
 * Infer environment from backend base URL.
 *
 * Security: Uses proper URL parsing to prevent malicious URLs from matching
 * via path/query components (e.g., "https://evil.com/localhost" should not match localhost).
 *
 * @param backendUrl - Backend base URL (e.g., "http://localhost:8787", "https://api-staging.navralabs.com")
 * @returns Environment name
 */
export function inferEnvironment(backendUrl: string): Environment {
  try {
    const url = new URL(backendUrl);
    const hostname = url.hostname.toLowerCase();

    // Dev: localhost or 127.0.0.1
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'dev';
    }

    // Staging: hostname contains "staging"
    // Use includes() for staging to match both "api-staging.navralabs.com" and "staging.navralabs.com"
    if (hostname.includes('staging')) {
      return 'staging';
    }

    // Production: exact hostname match for known production domains
    const PRODUCTION_DOMAINS = ['api.navralabs.com', 'app.navralabs.com', 'navralabs.com'];
    if (PRODUCTION_DOMAINS.includes(hostname)) {
      return 'production';
    }

    // Default to dev for safety (unrecognized URLs should not use production credentials)
    console.warn(`Unrecognized backend URL hostname: ${hostname}, defaulting to dev environment`);
    return 'dev';
  } catch (error) {
    // Invalid URL format - default to dev for safety
    console.warn(`Invalid backend URL format: ${backendUrl}, defaulting to dev environment`, error);
    return 'dev';
  }
}

/**
 * Get Auth0 configuration for the given backend URL.
 *
 * @param backendUrl - Backend base URL
 * @returns Auth0 configuration
 */
export function getAuthConfig(backendUrl: string): AuthConfig {
  const environment = inferEnvironment(backendUrl);

  return {
    auth0Domain: AUTH0_ISSUER,
    clientId: AUTH0_CLIENT_IDS[environment],
    audience: AUTH0_AUDIENCES[environment],
    environment,
  };
}
