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
 * @param backendUrl - Backend base URL (e.g., "http://localhost:8787", "https://api-staging.navralabs.com")
 * @returns Environment name
 */
export function inferEnvironment(backendUrl: string): Environment {
  const url = backendUrl.toLowerCase();

  // Dev: localhost or 127.0.0.1
  if (url.includes('localhost') || url.includes('127.0.0.1')) {
    return 'dev';
  }

  // Staging: contains "staging" in hostname
  if (url.includes('staging') || url.includes('api-staging')) {
    return 'staging';
  }

  // Production: everything else
  return 'production';
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
