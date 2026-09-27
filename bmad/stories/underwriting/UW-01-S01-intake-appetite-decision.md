---
id: UW-01-S01
title: "Submission intake → appetite/eligibility → decision + audit (workbench core)"
status: Ready
type: Story
epic: underwriting
milestone: "UW — Underwriting v1"
estimate: 5
labels: [insurance-lob, underwriting, backend, python]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/ktayl-underwriting
project: 12
initiative: Insurance LOB
---

*As an* **underwriter**, *I want* to capture a risk submission and have it assessed against the appetite/
eligibility rules so that I get an **accept / refer / decline** decision with cited reasons and a full audit
trail — the core of the workbench (UW-01), before rating (UW-04) and bind (ADR-006).

## Scope (this slice)
- **Submission intake** — capture a risk submission (local entity model per ADR-002: counterparty + risk
  data for one starter LOB, e.g. commercial property: TIV, occupancy, location, requested cover).
- **Appetite/eligibility engine** — evaluate the submission against a **versioned, immutable** appetite
  ruleset (ADR-004): in-appetite LOB, TIV within authority band, no excluded activity/sanction flag →
  produce a decision `accept | refer | decline` with **reason codes** (refer when a limit/authority is
  exceeded → seam for committee UW-03).
- **Decision + audit trail** — persist the decision and an **append-only** audit entry (who/when/inputs/
  ruleset version/outcome). No AI in this slice (ADR-003 — extraction is a later, human-verified add).

## Out of scope (explicit — follow-on stories)
- Rating/pricing/quote (UW-04), bind to `ktayl-policy-service` (ADR-006), committee workflow/Temporal
  (UW-03), document extraction (AI), the Next.js UI. This slice is the **API + domain + persistence**.

## Acceptance criteria
- `POST /v1/submissions` creates a submission (validated Pydantic schema) → `201` + id.
- `POST /v1/submissions/{id}/assess` runs the appetite engine → persists a `Decision`
  (`accept|refer|decline` + reason codes + appetite ruleset version) → returns it.
- `GET /v1/submissions/{id}` and `GET /v1/submissions/{id}/audit` return the file + append-only audit log.
- Appetite rulesets are **versioned + immutable** (a new version, never in-place edit); the decision records
  which version it used.
- The entity/appetite modules sit **behind interfaces** (ADR-002/001) so MDM/rating can slot in later.
- Tests: L0 (ruff + mypy) green; L1 (pytest) covers the appetite rules (accept/refer/decline paths) + the
  endpoints (happy + one failure each), ≥70% on business logic.

## Notes / architecture refs
- Stack per ADR-007: Python 3.12 + FastAPI + Pydantic + SQLAlchemy + Alembic on Postgres.
- Modular monolith (ADR-001): modules `submission`, `entity`, `appetite`, `decision`, `audit`.
- Follows `docs/architecture/solution-architecture.md` C4 (the `underwriting-api` container).
