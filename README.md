# ktayl-underwriting

[![CI](https://github.com/andrelair-platform/ktayl-underwriting/actions/workflows/ci.yml/badge.svg)](https://github.com/andrelair-platform/ktayl-underwriting/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)

> **Underwriting & pricing** for the ktayl-solution insurance IS — the UW workbench, guidelines,
> technical committee, rating/pricing and delegated authority. A Python modular-monolith service
> (ADR-001) that owns the underwriting file and, in later slices, binds risk into the live
> `ktayl-policy-service`. This repo currently ships the **S001 workbench core**.

**Product board:** https://github.com/orgs/andrelair-platform/projects/12
**Initiative:** Insurance LOB · **Layer:** ktayl-solution IS (business context, not the certification)
**Platform docs:** https://andrelair-platform.github.io/minicloud-platform-docs/

## The S001 slice (UW-01-S01)

The workbench core — **submission intake → appetite/eligibility assessment → decision + append-only
audit** — as API + domain + persistence only. Everything downstream is deferred: rating/pricing/quote
(UW-04), bind to `ktayl-policy-service` (ADR-006), the committee workflow / Temporal (UW-03), AI
document extraction (ADR-003), and the Next.js UI.

**Flow:** create a submission (a `commercial_property` risk with a local counterparty) → assess it
against the **current versioned, immutable appetite ruleset** (ADR-004) → persist a `Decision`
(`accept | refer | decline` + reason codes + the ruleset version used) and append an audit entry.

## Domain modules (modular monolith — ADR-001)

| Module | Responsibility |
|---|---|
| `entity` | Local `Counterparty` (ADR-002 — local now, MDM #20 later) behind a repository `Protocol` |
| `submission` | The risk `Submission` for the starter LOB `commercial_property`; `tiv_eur` is **eurocents** (BIGINT minor units) |
| `appetite` | **Versioned, immutable** `AppetiteRuleset` + a pure `assess(facts, ruleset) -> (outcome, reason_codes)` engine |
| `decision` | Persisted `Decision` (outcome, reason codes, appetite version, decided_by/at) |
| `rating` | **Versioned, immutable** `RateTable` + a pure `rate(facts, rate_table) -> QuoteBreakdown` engine; persisted `Quote` (UW-04-S01) |
| `bind` | Binds an accepted + quoted risk into the live `ktayl-policy-service` (ADR-006) + emits the bound-risk NATS event; persisted `Binding` (UW-01-S02). All external effects (PAS client / publisher / token provider) sit behind `Protocol` interfaces, injected via `Depends` |
| `audit` | **Append-only** `AuditEntry` (never updated/deleted) |

## Appetite engine

Pure and unit-testable (no I/O). Outcome ∈ `{accept, refer, decline}`. Hard declines take precedence
over refers. Reason codes are stable strings:

| Reason code | Outcome | When |
|---|---|---|
| `SANCTIONED_COUNTRY` | decline | risk country is on the ruleset's sanctioned set |
| `EXCLUDED_OCCUPANCY` | decline | occupancy is in the excluded set (e.g. `fireworks_manufacturing`) |
| `LOB_OUT_OF_APPETITE` | refer | LOB not in the ruleset's allowed set |
| `TIV_ABOVE_AUTHORITY` | refer | `tiv_eur` above the authority band (seam for committee UW-03) |
| `WITHIN_APPETITE` | accept | allowed LOB, within authority, no exclusion/sanction |

The **v1 ruleset** (seeded at migration + startup if none exists): allowed LOB `commercial_property`;
max TIV **€10,000,000** (= `1_000_000_000` eurocents, accepted at the boundary); excluded occupancy
`fireworks_manufacturing`; sanctioned countries `KP, IR, SY, RU`. Rulesets are **never edited in place**
— a change is a new version row.

## Rating engine (UW-04-S01)

Pure and unit-testable (no I/O), mirroring the appetite engine: `rate(facts, rate_table) -> QuoteBreakdown`.
Technical premium = `base_rate‰/1000 × TIV × occupancy_factor`, then the **ordered** loadings/discounts.
Money is **eurocents** (int); arithmetic runs on a high-precision `Decimal` and is rounded **once** at the
end so the breakdown reconciles exactly to the premium. The breakdown is an ordered list of line items
`{label, kind (base|factor|loading|discount), value, running_subtotal_minor}` + the final `premium_minor` —
human- and auditor-legible. A `Quote` records which `RateTable` version priced it; re-quoting inserts a new
row (latest wins). Rate tables are **versioned + immutable** (a change is a new version row).

The **v1 rate table** (commercial_property; seeded at migration + startup if none exists): base rate
**0.5‰** of TIV; occupancy factors `office 1.0 · retail 1.1 · warehouse 1.25 · light_manufacturing 1.5 ·
fireworks_manufacturing 3.0`; ordered adjustments `high_tiv_loading +10%` (TIV > €5,000,000) then
`sprinklered_discount −5%` (requested-cover text mentions a sprinkler). Both adjustment flags are derived
from existing submission fields — no new submission columns.

## Bind — hand a risk to the live policy service (UW-01-S02, ADR-006)

Bind is the cross-service handoff: an **accepted + quoted** risk is turned into an active policy in the
live `ktayl-policy-service` (a separate Go service — bound against **as-is**, no change to it) and a
**bound-risk event** is emitted (the reinsurance/actuarial seam). It is a **3-step PAS lifecycle**, not
one call:

1. `POST /v1/policies` `{policy_number, holder_name, product_code, effective_date, expiry_date}` → `draft`
2. `POST /v1/policies/{id}/submit` → `submitted`
3. `POST /v1/policies/{id}/activate` → **active** (= bind)

Every external effect sits behind a `typing.Protocol` injected via `Depends`, so **L1 runs with no
network**: `PolicyServiceClient` (httpx, `POLICY_SERVICE_URL`), `TokenProvider` (OAuth2
client-credentials against Authentik, scope `policy:write`, in-memory cached), and `BoundRiskPublisher`
(nats-py, `NATS_URL`, subject `insurance.underwriting.bound-risk`).

**Idempotency (ADR-006), three layers:** a **deterministic `policy_number = UW-<sha1(quote_id)[:12]>`**
(pure, unit-tested) → a PAS `409` on a duplicate create is treated as **success** (the client resolves
the existing id and continues) → and if a UW `Binding` already exists for the submission, bind is a
**no-op** returning it (no PAS calls, no duplicate event). Premium/terms stay in the UW record, linked to
the policy by `policy_number` (ADR-006 accepted limitation: the thin PAS `CreatePolicyRequest` carries no
premium/terms yet).

The **bound-risk event** shape: `{policy_number, submission_id, quote_id, premium_minor, currency,
product_code, effective_date, expiry_date}`. Publishing is **best-effort** — a publish failure never
fails an already-activated bind (it is logged, recorded in the audit detail, and `event_published` stays
`false`). **CreatePolicyRequest mapping:** `holder_name` = the submission's counterparty name;
`product_code` from a LOB map (`commercial_property → COMM_PROP`); `effective_date`/`expiry_date` default
to today → +1 year (v1 assumption — the thin intake carries no cover dates yet).

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/v1/submissions` | Create a submission → `201` + id |
| POST | `/v1/submissions/{id}/assess` | Run the appetite engine, persist `Decision` + audit → returns the decision (`404` if missing) |
| POST | `/v1/submissions/{id}/quote` | Price the submission against the current rate table, persist `Quote` + audit → returns quote + breakdown. **Guard:** latest decision `decline` → `409`; missing submission/decision → `404` |
| GET | `/v1/submissions/{id}/quote` | The latest quote (+ breakdown) (`404` if none) |
| POST | `/v1/submissions/{id}/bind` | Bind the accepted + quoted risk into the live policy service (create→submit→activate) + emit the bound-risk event → returns the `Binding`. **Guard:** latest decision must be `accept` and a quote must exist (`422` otherwise); `404` if missing. **Idempotent** re-bind returns the existing binding (no duplicate PAS calls/event) |
| GET | `/v1/submissions/{id}/bind` | The binding for a submission (`404` if not bound) |
| GET | `/v1/rate-tables` | The rate-table versions |
| GET | `/v1/submissions/{id}` | The submission + its latest decision (`404` if missing) |
| GET | `/v1/submissions/{id}/audit` | The append-only audit log (`404` if the submission is missing) |
| GET | `/healthz` | Liveness |
| GET | `/info` | Service name + version (from `version.txt`) |

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x · Alembic · PostgreSQL · uvicorn (ADR-007).
Modular monolith (ADR-001); modules behind repository `Protocol` interfaces so MDM/rating slot in later.

## Getting started

```bash
python -m venv .venv && . .venv/bin/activate
make install          # pip install -e ".[test]"
make test             # L1: pytest --cov (SQLite in-memory — no Docker/network) --cov-fail-under=70
make lint             # L0: ruff check + ruff format --check + mypy
make run              # uvicorn dev server on :8000 (uses DATABASE_URL or a dev default)
```

Apply the schema to a real Postgres:

```bash
export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/underwriting"
make migrate          # alembic upgrade head (creates tables + seeds appetite ruleset v1)
```

**Self-migrate on startup (the platform standard).** In-cluster the app migrates itself: on startup
(FastAPI lifespan) it waits for the DB to accept connections, runs `alembic upgrade head`, then seeds
appetite ruleset v1 — all idempotent — before serving. This avoids a separate Alembic migration Job,
which would deadlock the ArgoCD sync ordering (the Job depends on the CNPG DB created in the same
sync). The behaviour is gated by `RUN_DB_MIGRATIONS_ON_STARTUP` (default `true`); the L1 test suite
sets it `false` and builds the schema in-memory instead. `make migrate` above stays available for
running migrations manually against any Postgres.

`DATABASE_URL` is read at runtime (env-agnostic image). Tests run without Postgres: the appetite
engine tests are pure and the API tests use a `TestClient` with the DB dependency overridden to a
SQLite in-memory session.

## Architecture & planning docs

- [Solution architecture](docs/architecture/solution-architecture.md) · [ADR log](docs/architecture/adr/000-index.md) · [NFR register](docs/architecture/nfr-register.md) · [Threat model](docs/architecture/threat-model.md)
- [Brief](docs/brief.md) · [PRD](docs/prd.md) · [Sprint plan](docs/uw-v1-sprint-plan.md) · [FDE playbook](docs/fde-underwriting-playbook.md)
- BMAD stories live in `bmad/stories/underwriting/` and sync to Issues on **Project #12** via the
  org-shared reusable workflow.

## Epic backlog

| ID | Epic | Priority |
|---|---|---|
| UW-01 | Underwriting workbench | P1 |
| UW-02 | Underwriting guidelines repository | P2 |
| UW-03 | Technical underwriting committee / escalation | P2 |
| UW-04 | Pricing / rating engine | P2 |
| UW-05 | Catastrophe modelling / aggregate exposure | P3 |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — trunk-based (`dev` + `main`), conventional commits, GPG-signed
`main` PRs, CI must be green.

## License

MIT — see [LICENSE](LICENSE).
