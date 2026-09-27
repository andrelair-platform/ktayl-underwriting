---
id: UW-04-S01
title: "Rating engine + explainable quote (versioned rate tables)"
status: Ready
type: Story
epic: underwriting
milestone: "UW — Underwriting v1"
estimate: 5
labels: [insurance-lob, underwriting, backend, python, pricing]
priority: P2
assignee: AndreLiar
repo: andrelair-platform/ktayl-underwriting
project: 12
initiative: Insurance LOB
---

*As an* **underwriter**, *I want* to price an assessed submission into a **quote with an explainable
premium breakdown**, computed from **versioned rate tables** *so that* I can offer a technically-grounded,
auditor-legible price — the step after appetite (UW-01-S01) and before bind (ADR-006).

## Scope (this slice — commercial_property LOB)
- **Versioned, immutable rate tables** (ADR-004, same control-library pattern as the appetite ruleset):
  a rate table has a `version`, `effective_at`, and rules — base rate (per mille of TIV), occupancy
  factors, and named loadings/discounts. New version = new row; never edit in place. Seed **version 1**.
- **Pure `rate()` engine** (I/O-free, exhaustively unit-testable — the numpy/pandas home turf that drove
  the Python stack choice, ADR-007): `rate(facts, rate_table) -> QuoteBreakdown`. Technical premium =
  `base_rate × TIV × occupancy_factor`, then apply ordered loadings/discounts. Money = **eurocents** (int),
  rounded once at the end. FR-4.2: return an **explainable breakdown** — an ordered list of line items
  (label, factor/amount, running subtotal) so the premium is human- and auditor-legible.
- **Quote** entity persisted against the submission: premium (minor units), rate-table version, the
  breakdown (JSON), currency EUR, created_by/at. A submission may be re-quoted (new Quote row; latest wins).

## Endpoints (extend /v1)
- `POST /v1/submissions/{id}/quote` → rate the submission against the current rate-table version, persist a
  `Quote` + an audit entry, return the quote with its breakdown. **Guard:** only a submission whose latest
  decision is `accept` or `refer` may be quoted (a `decline` → `409`); `404` if submission/decision missing.
- `GET /v1/submissions/{id}/quote` → the latest quote (+ breakdown). `GET /v1/rate-tables` → versions.

## Out of scope (follow-on)
- Rate-adequacy KPI signal (FR-4.3), multi-LOB rate tables, committee/authority interplay (UW-03), bind
  to policy-service (ADR-006 — the NEXT story), the UI. This slice = the rating engine + quote API.

## Acceptance criteria
- `rate()` is pure + deterministic; unit tests cover base premium, occupancy factor, each loading/discount,
  ordering, rounding, and that the breakdown line items **sum to the final premium**.
- Rate tables are versioned + immutable; the quote records which version priced it (auditability NFR).
- The quote guard (no quoting a declined risk) is enforced + tested; audit entry written on quote.
- Reuses the S001 shape: modular monolith module `rating`, behind an interface; L0 ruff+mypy green; L1
  pytest ≥70% (accept→quote happy path + decline→409 + engine unit tests), no Docker (SQLite in-memory).

## Notes
- Same stack/patterns as UW-01-S01. Premium computation NFR: p95 < 800ms (trivially met — pure arithmetic).
- The premium this produces is what later makes the Data Platform's GWP authoritative (closes DP-007) and
  what ADR-006 bind will carry to the policy record.
