"""Test helpers for the optional JWKS auth — mint RS256 tokens + a fake JWKS client (no network).

The real ``PyJWKClient`` fetches keys over HTTP; L1 must not touch the network. These helpers generate
an in-process RSA keypair, sign JWTs with the private key, and expose a ``FakePyJWKClient`` that returns
the matching public key so ``jwt.decode`` verifies the signature exactly as it would in prod — only the
key *transport* is faked, the crypto is real.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

# One keypair for the whole test session — generating RSA is the only slow bit.
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


@dataclass
class _FakeSigningKey:
    key: Any


class FakePyJWKClient:
    """Stands in for ``jwt.PyJWKClient`` — always returns the test public key (no HTTP)."""

    def __init__(self, url: str) -> None:  # signature-compatible with PyJWKClient
        self._url = url

    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(key=_PUBLIC_KEY)


def make_token(
    *,
    scope: str = "underwriting:read underwriting:write",
    preferred_username: str | None = "alice@ktayl",
    email: str | None = None,
    sub: str = "user-123",
    expired: bool = False,
    unsigned_garbage: bool = False,
) -> str:
    """Mint an RS256 JWT for tests. ``expired`` backdates exp; ``unsigned_garbage`` returns junk."""
    if unsigned_garbage:
        return "not.a.valid.jwt"
    now = int(time.time())
    exp = now - 60 if expired else now + 3600
    claims: dict[str, Any] = {"sub": sub, "scope": scope, "iat": now, "exp": exp}
    if preferred_username is not None:
        claims["preferred_username"] = preferred_username
    if email is not None:
        claims["email"] = email
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256")
