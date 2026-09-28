"""Unit tests for the optional per-endpoint auth (app/api/auth.py) — no network.

Covers ``require_scope`` + ``current_actor`` + the claim parsers directly, plus the auth-OFF/ON
toggle. The JWKS *transport* is faked (FakePyJWKClient) but the RS256 signature check is real.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

import app.api.auth as auth
from app.api.auth import (
    DEV_ACTOR,
    _actor_from_claims,
    _scopes_from_claims,
    current_actor,
    require_scope,
)
from app.config import get_settings
from tests.fixtures.auth import FakePyJWKClient, make_token


def _request(authorization: str | None = None) -> Request:
    """A minimal ASGI Request carrying an optional Authorization header."""
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    scope = {"type": "http", "method": "GET", "path": "/", "headers": headers}
    return Request(scope)


def _dependency(required: str):  # unwrap the Depends() wrapper to call the callable directly
    return require_scope(required).dependency


@pytest.fixture
def auth_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn auth ON on the cached settings + point the JWKS client at the in-process fake key."""
    monkeypatch.setattr(get_settings(), "authentik_jwks_url", "https://auth.example/jwks")
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakePyJWKClient(url))


# --- claim parsers ----------------------------------------------------------


def test_scopes_from_claims_splits_space_delimited() -> None:
    assert _scopes_from_claims({"scope": "a b c"}) == {"a", "b", "c"}
    assert _scopes_from_claims({}) == set()
    assert _scopes_from_claims({"scope": 123}) == set()  # non-string is ignored


def test_actor_precedence_username_then_email_then_sub() -> None:
    assert _actor_from_claims({"preferred_username": "u", "email": "e", "sub": "s"}) == "u"
    assert _actor_from_claims({"email": "e", "sub": "s"}) == "e"
    assert _actor_from_claims({"sub": "s"}) == "s"
    assert _actor_from_claims({}) == "unknown"


# --- auth OFF (no JWKS url) → open ------------------------------------------


def test_require_scope_off_is_passthrough() -> None:
    # conftest leaves AUTHENTIK_JWKS_URL empty by default in these unit tests (settings default "").
    assert get_settings().authentik_jwks_url == ""
    assert _dependency("underwriting:read")(_request()) == DEV_ACTOR


def test_current_actor_off_is_dev_placeholder() -> None:
    assert current_actor(_request()) == DEV_ACTOR


# --- auth ON ----------------------------------------------------------------


def test_require_scope_on_missing_token_401(auth_on: None) -> None:
    with pytest.raises(HTTPException) as exc:
        _dependency("underwriting:read")(_request())
    assert exc.value.status_code == 401


def test_require_scope_on_invalid_token_401(auth_on: None) -> None:
    token = make_token(unsigned_garbage=True)
    with pytest.raises(HTTPException) as exc:
        _dependency("underwriting:read")(_request(f"Bearer {token}"))
    assert exc.value.status_code == 401


def test_require_scope_on_expired_token_401(auth_on: None) -> None:
    token = make_token(expired=True)
    with pytest.raises(HTTPException) as exc:
        _dependency("underwriting:read")(_request(f"Bearer {token}"))
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail


def test_require_scope_on_wrong_scope_403(auth_on: None) -> None:
    token = make_token(scope="underwriting:read")  # lacks :write
    with pytest.raises(HTTPException) as exc:
        _dependency("underwriting:write")(_request(f"Bearer {token}"))
    assert exc.value.status_code == 403


def test_require_scope_on_right_scope_returns_actor(auth_on: None) -> None:
    token = make_token(scope="underwriting:write", preferred_username="bob@ktayl")
    actor = _dependency("underwriting:write")(_request(f"Bearer {token}"))
    assert actor == "bob@ktayl"


def test_current_actor_on_extracts_email_then_sub(auth_on: None) -> None:
    token = make_token(preferred_username=None, email="carol@ktayl")
    assert current_actor(_request(f"Bearer {token}")) == "carol@ktayl"
    token2 = make_token(preferred_username=None, email=None, sub="sub-only")
    assert current_actor(_request(f"Bearer {token2}")) == "sub-only"
