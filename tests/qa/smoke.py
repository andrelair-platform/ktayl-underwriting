#!/usr/bin/env python3
"""L4 smoke / QA-gate harness — adversarial end-to-end checks against a RUNNING ktayl-underwriting.

Standalone (only stdlib + httpx, which the image already ships) and ``BASE_URL``-parametrized, so the
same script runs against local (``http://localhost:8000``), the dev ingress, or in-cluster via
``kubectl exec -i <pod> -- python - < tests/qa/smoke.py``. It is NOT part of the unit CI (it needs a
live service); it is the **promotion / QA gate** smoke — run it post-deploy against the live dev
service before promoting.

It mirrors an adversarial QA pass over the whole surface:
  - all three appetite outcomes (accept / refer / decline),
  - the pricing breakdown reconciles to the premium,
  - validation errors return 4xx (not 5xx),
  - 404s for unknown ids on every read,
  - ordering guards (quote-before-assess, bind-before-quote),
  - the bind happy path + idempotent re-bind (same binding id, no duplicate),
  - the bound-file lock (re-assess / re-quote after bind → 409).

Each check prints ``PASS``/``FAIL``; a failed **BLOCKER** check makes the process exit non-zero so it
can gate a promotion. Non-blocker checks (marked ``[warn]``) report but don't fail the gate.

Usage:
    BASE_URL=https://ktayl-underwriting-dev.10.0.0.200.nip.io python tests/qa/smoke.py
    python tests/qa/smoke.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"

_PASS = 0
_FAIL = 0
_BLOCKER_FAIL = 0


def _record(name: str, ok: bool, *, blocker: bool = True, detail: str = "") -> bool:
    global _PASS, _FAIL, _BLOCKER_FAIL
    tag = "PASS" if ok else "FAIL"
    lane = "" if blocker else " [warn]"
    line = f"[{tag}]{lane} {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    if ok:
        _PASS += 1
    else:
        _FAIL += 1
        if blocker:
            _BLOCKER_FAIL += 1
    return ok


def _submission_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "counterparty": {"name": "Smoke Test SAS", "country": "FR"},
        "line_of_business": "commercial_property",
        "tiv_eur": 500_000_00,
        "occupancy": "warehouse",
        "country": "FR",
        "postcode": "75001",
        "requested_cover": "All-risks property damage + business interruption",
        "broker_ref": "SMOKE-001",
    }
    body.update(overrides)
    return body


def _create(client: httpx.Client, **overrides: Any) -> str:
    resp = client.post("/v1/submissions", json=_submission_body(**overrides))
    resp.raise_for_status()
    return str(resp.json()["id"])


# --- checks -----------------------------------------------------------------


def check_health(client: httpx.Client) -> None:
    r = client.get("/healthz")
    _record("healthz returns 200 ok", r.status_code == 200 and r.json().get("status") == "ok")
    r = client.get("/info")
    _record("info reports the service name", r.status_code == 200 and r.json().get("service") == "ktayl-underwriting")


def check_accept_journey(client: httpx.Client) -> None:
    sub_id = _create(client)
    dec = client.post(f"/v1/submissions/{sub_id}/assess")
    _record(
        "assess (warehouse €500k FR) → accept",
        dec.status_code == 200 and dec.json()["outcome"] == "accept",
        detail=f"status={dec.status_code}",
    )
    q = client.post(f"/v1/submissions/{sub_id}/quote")
    ok_q = q.status_code == 200 and q.json()["premium_minor"] == 31_250
    premium = q.json().get("premium_minor") if q.status_code == 200 else q.status_code
    _record("quote → €312.50 (31_250 minor)", ok_q, detail=f"premium={premium}")
    if q.status_code == 200:
        body = q.json()
        recon = body["breakdown"][-1]["running_subtotal_minor"] == body["premium_minor"]
        _record("quote breakdown reconciles to premium", recon)
    b = client.post(f"/v1/submissions/{sub_id}/bind")
    ok_b = b.status_code == 200 and b.json()["status"] == "bound" and str(b.json()["policy_number"]).startswith("UW-")
    _record("bind → bound policy (UW-…)", ok_b, detail=f"status={b.status_code}")


def check_refer_and_decline(client: httpx.Client) -> None:
    # above authority → refer (quotable, not bindable)
    refer_id = _create(client, tiv_eur=2_000_000_000)
    dec = client.post(f"/v1/submissions/{refer_id}/assess")
    _record("assess (above authority) → refer", dec.status_code == 200 and dec.json()["outcome"] == "refer")
    _record("refer is quotable", client.post(f"/v1/submissions/{refer_id}/quote").status_code == 200)
    _record("refer is NOT bindable (422)", client.post(f"/v1/submissions/{refer_id}/bind").status_code == 422)

    # sanctioned country → decline (not quotable)
    decline_id = _create(client, country="KP")
    dec = client.post(f"/v1/submissions/{decline_id}/assess")
    _record("assess (sanctioned KP) → decline", dec.status_code == 200 and dec.json()["outcome"] == "decline")
    quoted = client.post(f"/v1/submissions/{decline_id}/quote")
    _record("declined risk is NOT quotable (409)", quoted.status_code == 409)


def check_validation_and_404s(client: httpx.Client) -> None:
    r = client.post("/v1/submissions", json=_submission_body(tiv_eur=0))
    _record("invalid submission (tiv_eur=0) → 422 (not 5xx)", r.status_code == 422, detail=f"status={r.status_code}")

    for path in (
        "/v1/submissions/does-not-exist",
        "/v1/submissions/does-not-exist/quote",
        "/v1/submissions/does-not-exist/bind",
        "/v1/submissions/does-not-exist/audit",
    ):
        _record(f"GET {path} → 404", client.get(path).status_code == 404)
    _record(
        "assess unknown submission → 404",
        client.post("/v1/submissions/does-not-exist/assess").status_code == 404,
    )


def check_ordering_guards(client: httpx.Client) -> None:
    # quote before assess → 404 (no decision)
    sub_id = _create(client)
    _record("quote before assess → 404", client.post(f"/v1/submissions/{sub_id}/quote").status_code == 404)
    # bind before quote (assessed accept but not quoted) → 422
    client.post(f"/v1/submissions/{sub_id}/assess")
    _record("bind before quote → 422", client.post(f"/v1/submissions/{sub_id}/bind").status_code == 422)


def check_idempotency_and_lock(client: httpx.Client) -> None:
    sub_id = _create(client)
    client.post(f"/v1/submissions/{sub_id}/assess")
    client.post(f"/v1/submissions/{sub_id}/quote")
    first = client.post(f"/v1/submissions/{sub_id}/bind")
    second = client.post(f"/v1/submissions/{sub_id}/bind")
    same = first.status_code == 200 and second.status_code == 200 and first.json()["id"] == second.json()["id"]
    _record("re-bind is idempotent (same binding id)", same)

    # bound file is locked: re-assess / re-quote → 409
    reassess = client.post(f"/v1/submissions/{sub_id}/assess")
    _record("re-assess after bind → 409 (bound file locked)", reassess.status_code == 409)
    requote = client.post(f"/v1/submissions/{sub_id}/quote")
    _record("re-quote after bind → 409 (bound file locked)", requote.status_code == 409)


def main() -> int:
    parser = argparse.ArgumentParser(description="ktayl-underwriting L4 smoke / QA-gate harness")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", DEFAULT_BASE_URL),
        help="base URL of the running service (env BASE_URL, default http://localhost:8000)",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="per-request timeout seconds")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed CA)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"== ktayl-underwriting smoke — target {base_url} ==")

    verify = not args.insecure
    try:
        with httpx.Client(base_url=base_url, timeout=args.timeout, verify=verify) as client:
            check_health(client)
            check_accept_journey(client)
            check_refer_and_decline(client)
            check_validation_and_404s(client)
            check_ordering_guards(client)
            check_idempotency_and_lock(client)
    except httpx.HTTPError as exc:
        print(f"[FAIL] transport error talking to {base_url}: {exc}")
        return 2

    print(f"\n== {_PASS} passed, {_FAIL} failed ({_BLOCKER_FAIL} blocker) ==")
    return 1 if _BLOCKER_FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
