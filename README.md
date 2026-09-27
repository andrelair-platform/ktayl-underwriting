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

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/v1/submissions` | Create a submission → `201` + id |
| POST | `/v1/submissions/{id}/assess` | Run the appetite engine, persist `Decision` + audit → returns the decision (`404` if missing) |
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
