// Server-only BFF token provider. Mirrors the backend's app/bind/token.py ClientCredentialsTokenProvider:
// mint an Authentik OAuth2 **client-credentials** token (scope = underwriting:read underwriting:write)
// and cache it in memory until shortly before expiry. The workbench backend enforces per-endpoint JWT
// scope authz when AUTHENTIK_JWKS_URL is set (prod); the BFF must therefore present a scoped bearer token.
//
// Config is read from server-side env at RUNTIME (never baked). When the OIDC vars are absent (dev, where
// the backend runs auth-OFF) getApiToken() returns null → no Authorization header, matching dev behaviour.

// Refresh a little before actual expiry to avoid a race on a call that starts near expiry (matches backend).
const EXPIRY_SKEW_MS = 30_000;
// Fallback lifetime if the token endpoint omits expires_in (matches backend's 300s default).
const DEFAULT_TTL_MS = 300_000;

interface OidcConfig {
  tokenUrl: string;
  clientId: string;
  clientSecret: string;
  scope: string;
}

function readConfig(): OidcConfig | null {
  const tokenUrl = process.env.OIDC_TOKEN_URL;
  const clientId = process.env.OIDC_CLIENT_ID;
  const clientSecret = process.env.OIDC_CLIENT_SECRET;
  const scope = process.env.OIDC_SCOPE;
  if (!tokenUrl || !clientId || !clientSecret || !scope) return null;
  return { tokenUrl, clientId, clientSecret, scope };
}

let cachedToken: string | null = null;
let expiresAtMs = 0;

/** Test seam: clear the in-memory cache between cases. */
export function _resetTokenCacheForTests(): void {
  cachedToken = null;
  expiresAtMs = 0;
}

/**
 * The bearer token the BFF attaches to backend calls, or null when auth is not configured (dev).
 * Caches in memory until ~EXPIRY_SKEW before expiry. `now` is injectable for tests.
 */
export async function getApiToken(now: () => number = Date.now): Promise<string | null> {
  const cfg = readConfig();
  if (!cfg) return null; // auth OFF (dev) — backend has no AUTHENTIK_JWKS_URL, so no header needed

  const t = now();
  if (cachedToken !== null && t < expiresAtMs - EXPIRY_SKEW_MS) {
    return cachedToken;
  }

  const res = await fetch(cfg.tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: cfg.clientId,
      client_secret: cfg.clientSecret,
      scope: cfg.scope,
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`OIDC token endpoint returned ${res.status}`);
  }
  const body = (await res.json()) as { access_token: string; expires_in?: number };
  cachedToken = body.access_token;
  expiresAtMs = t + (body.expires_in != null ? body.expires_in * 1000 : DEFAULT_TTL_MS);
  return cachedToken;
}
