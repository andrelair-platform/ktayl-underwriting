"""TokenProvider — the seam that yields an OIDC access token (scope ``policy:write``) for PAS calls.

The interface is a ``typing.Protocol`` so tests inject a fake and L1 never touches the network. The
real impl fetches a token via the OAuth2 **client-credentials** grant (Authentik) with httpx and
caches it in memory until shortly before expiry. Bind auth is service-to-service (ADR-006), so
client-credentials — not a user token — is correct.
"""

from __future__ import annotations

import time
from typing import Protocol

import httpx

# Refresh a little before the token actually expires to avoid a race on a call that starts near expiry.
_EXPIRY_SKEW_SECONDS = 30.0
# Fallback lifetime if the token endpoint omits expires_in.
_DEFAULT_TTL_SECONDS = 300.0


class TokenProvider(Protocol):
    """Yields a bearer token carrying the ``policy:write`` scope."""

    def token(self) -> str: ...


class ClientCredentialsTokenProvider:
    """OAuth2 client-credentials token provider (Authentik), with simple in-memory caching."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "policy:write",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._timeout_seconds = timeout_seconds
        self._cached: str | None = None
        self._expires_at: float = 0.0

    def token(self) -> str:
        now = time.monotonic()
        if self._cached is not None and now < self._expires_at - _EXPIRY_SKEW_SECONDS:
            return self._cached

        resp = httpx.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
            },
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
        access_token = str(body["access_token"])
        ttl = float(body.get("expires_in", _DEFAULT_TTL_SECONDS))
        self._cached = access_token
        self._expires_at = now + ttl
        return access_token
