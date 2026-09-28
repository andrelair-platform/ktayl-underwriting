"""Per-endpoint authz — optional JWKS-validated JWT bearer auth (mirrors ktayl-policy-service).

Auth is **off in dev/test, on in prod**, toggled purely by config (``AUTHENTIK_JWKS_URL``):

* **Empty** ``AUTHENTIK_JWKS_URL`` → auth **disabled**: ``require_scope`` is a no-op pass-through and
  ``current_actor`` resolves to the dev placeholder ``underwriter@ktayl``. This matches
  policy-service's "run without auth" and keeps the L1 suite network-free.
* **Set** → auth **enabled**: each protected route validates ``Authorization: Bearer <jwt>`` — the
  signature is verified against the Authentik JWKS and expiry is enforced (signature + exp only, no
  audience/issuer check, mirroring the Go middleware). The space-delimited ``scope`` claim must
  contain the endpoint's required scope, and the actor is taken from the token.

Failure mapping (auth on): 401 for a missing/invalid/expired token, 403 for a valid token that lacks
the required scope — the same contract as the policy-service Go middleware.
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.params import Depends as DependsType

from app.config import get_settings

# The dev/test fallback actor (used when auth is OFF) — kept identical to the router placeholder.
DEV_ACTOR = "underwriter@ktayl"


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Cache one PyJWKClient per JWKS url (module-level, keyed by url) so keys are fetched once."""
    return jwt.PyJWKClient(jwks_url)


def _decode(token: str, jwks_url: str) -> dict:
    """Validate signature + expiry against the JWKS and return the claims (no aud/iss check).

    Raises jwt.PyJWTError (incl. ExpiredSignatureError) on any validation failure.
    """
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        options={"verify_aud": False},
    )


def _bearer_token(request: Request) -> str:
    """Extract the raw JWT from the ``Authorization: Bearer <jwt>`` header, or 401 if absent."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization: Bearer header required",
        )
    return header[len("Bearer ") :]


def _actor_from_claims(claims: dict) -> str:
    """The caller identity = first present of preferred_username, email, sub."""
    for key in ("preferred_username", "email", "sub"):
        value = claims.get(key)
        if value:
            return str(value)
    return "unknown"


def _scopes_from_claims(claims: dict) -> set[str]:
    """The space-delimited ``scope`` claim as a set."""
    scope = claims.get("scope", "")
    if not isinstance(scope, str):
        return set()
    return set(scope.split())


def current_actor(request: Request) -> str:
    """The authenticated caller (auth ON), else the dev placeholder (auth OFF).

    When auth is on this validates the token the same way ``require_scope`` does; a missing/invalid/
    expired token → 401. Routes that also depend on ``require_scope`` have already validated the
    token, so this simply re-derives the actor from the same header.
    """
    jwks_url = get_settings().authentik_jwks_url
    if not jwks_url:
        return DEV_ACTOR
    token = _bearer_token(request)
    try:
        claims = _decode(token, jwks_url)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token validation failed") from None
    return _actor_from_claims(claims)


def require_scope(required: str) -> DependsType:
    """Build a FastAPI dependency enforcing ``required`` scope when auth is on; no-op when off.

    Auth OFF (empty JWKS url) → pass-through. Auth ON → 401 (missing/invalid/expired token),
    403 (valid token lacking ``required``). Returns the resolved actor so a route can reuse it.
    """

    def _dependency(request: Request) -> str:
        jwks_url = get_settings().authentik_jwks_url
        if not jwks_url:
            return DEV_ACTOR
        token = _bearer_token(request)
        try:
            claims = _decode(token, jwks_url)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has expired") from None
        except jwt.PyJWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token validation failed") from None
        if required not in _scopes_from_claims(claims):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"required scope: {required}")
        return _actor_from_claims(claims)

    return Depends(_dependency)
