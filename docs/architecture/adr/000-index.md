# ADR Log — Underwriting & Pricing (#12)

> **BMAD/SA artefact.** Index of architecture decisions + rationale so the "why" survives 6 months out.
> Each ADR: Status · Context · Decision · Consequences. **Status: DRAFT / Proposed — for review.**

| ADR | Title | Status | Owner |
|---|---|---|---|
| [001](#adr-001) | Modular monolith service for v1 (not microservices) | Proposed | SA/TL |
| [002](#adr-002) | Local entity model now; MDM (#20) later | Proposed | SA/TL |
| [003](#adr-003) | AI is assistive + human-verified only (no autonomous action) | Proposed | SA/TL |
| [004](#adr-004) | Rate tables & guidelines are versioned, immutable, auditable | Proposed | SA/TL |
| [005](#adr-005) | Temporal for referral/committee SLAs (UW-03) | Proposed | SA/TL |
| [006](#adr-006) | Bind contract to `ktayl-policy-service` = versioned API + NATS event | Proposed | SA/TL |
| [007](#adr-007) | Backend = Python + FastAPI; Frontend = Next.js + React | Proposed | SA/TL |

---

## ADR-001 — Modular monolith service for v1 {#adr-001}
**Context.** v1 is one narrow flow (the thin slice) for one LOB; boundaries between submission/guideline/
rating/decision aren't yet proven.
**Decision.** Ship **one modular service** (`ktayl-underwriting`) with clear internal modules, not a set of
microservices.
**Consequences.** Faster to build/operate solo; fewer moving parts at the gates. Split a module into its own
service only when a real seam (independent scaling/ownership) appears. Aligns with the platform's "Kargo
only when it earns it" discipline.

## ADR-002 — Local entity model now; MDM later {#adr-002}
**Context.** Client/broker/insured are shared master data, but **MDM (#20) is parked** (build-order: business
tools first).
**Decision.** UW-01 starts with a **local entity model**; refactor to MDM when a **second consumer** exists.
**Consequences.** No blocking dependency on standing up MDM. Accepted risk: entity duplication/quality across
domains until MDM (see threat T-residual). Keep the entity module behind an interface to ease the refactor.

## ADR-003 — AI assistive + human-verified only {#adr-003}
**Context.** EU AI Act tiers controls by impact; autonomous UW action is high-tier.
**Decision.** All v1 AI (submission extraction, guideline assist, routing) is **limited-tier**: it proposes,
a human confirms, and **no AI output is persisted to the file without human confirmation**. The **AI Ops
Copilot** (#19) that *acts* stays **parked** until its high-tier controls (DPIA, oversight, eval, monitoring,
contestability) are in place.
**Consequences.** Lower regulatory burden for v1; extraction is a productivity aid, not a decision-maker.
Prompt-injection risk (T8) is contained by treating extraction output as untrusted.

## ADR-004 — Versioned, immutable, auditable rate tables & guidelines {#adr-004}
**Context.** Solvency II + ACPR expect pricing and appetite rules to be auditable; mispricing/appetite bypass
is a critical-integrity risk (T2).
**Decision.** Rate tables and guidelines are **versioned like a control library** — every change is a new
immutable version with author + approval; the decision trail is append-only.
**Consequences.** Full pricing/appetite auditability and explainability (EXP/AUD NFRs). Slightly more schema
complexity; no in-place edits.

## ADR-005 — Temporal for referral/committee SLAs {#adr-005}
**Context.** UW-03 (deferred) needs SLA-tracked escalation with durable state.
**Decision.** Use the platform's **Temporal** for the referral/committee workflow when UW-03 is built.
**Consequences.** Durable, observable SLAs without bespoke state machines. Recorded now so the workbench
leaves the right seam; no v1 work.

## ADR-006 — Bind contract to `ktayl-policy-service` {#adr-006}
**Context.** Bind is the cross-service handoff to the live PAS and the trigger for downstream reinsurance/
actuarial.
**Decision.** The bind is an **explicit versioned API contract** to `ktayl-policy-service` **plus a NATS
bound-risk event**; the call is authenticated (mTLS/OIDC), idempotent, and validated by PAS.
**Consequences.** Clean, testable handoff (contract test); downstream consumers get clean event-published
bound-risk data. Defining this early is a v1 priority (Brief goal 2).

## ADR-007 — Backend = Python + FastAPI; Frontend = Next.js + React {#adr-007}
**Context.** The [stack-selection rule](https://github.com/andrelair-platform/minicloud-gitops/blob/main/.claude/rules/tech-stack-selection.md)
says pick the best-fit stack per project (not a house default of Go). This domain's hard parts are
**numeric pricing/rating** (rate tables, factor math) and a **document-extraction pipeline** (Docling/
markitdown/LLM) — both native to Python — plus a rich, typed, auditable domain.
**Decision.** **Backend = Python 3.12 + FastAPI + Pydantic** (SQLAlchemy + Alembic on Postgres; numpy/pandas
for rating; a Python extraction worker). **Frontend = Next.js + React** (PWA only if a mobile/offline need
is real). The bind call to `ktayl-policy-service` is over HTTP, so its stack is independent (ADR-006).
**Consequences.** Rating and extraction live in their home ecosystem; Pydantic gives typed API contracts.
Adds Python to the LOB alongside other services' languages (deliberate variety, per the rule). Trade-off:
a heavy transactional domain is arguably Java/Spring territory — accepted, because the pricing + AI/document
weight of *this* domain outweighs it, and ADR-001 keeps it a single modular service. Revisit if a
transactional-integrity seam later dominates.
