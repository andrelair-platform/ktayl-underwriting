// BFF token provider — thin wrapper over the shared @andrelair-platform/bff-auth library (this repo is
// consumer #1). The client-credentials minting + caching logic now lives in the package (tested there);
// here we just wire it from env (OIDC_TOKEN_URL / OIDC_CLIENT_ID / OIDC_CLIENT_SECRET / OIDC_SCOPE).
// Returns null when those are unset (dev / backend auth-off) → no Authorization header is sent.
import "server-only";

import { tokenProviderFromEnv } from "@andrelair-platform/bff-auth";

/** Resolves the bearer token for backend calls, or null when auth is not configured (dev). */
export const getApiToken = tokenProviderFromEnv();
