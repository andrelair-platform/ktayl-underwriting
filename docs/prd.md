# PRD — Underwriting & Pricing (ktayl-underwriting, board #12)

> **BMAD artefact — PRODUCT CONTRACT.** What the product must do and to what standard. Derived from the
> [Brief](./brief.md) and the [FDE Playbook](./fde-underwriting-playbook.md).
> **Status: DRAFT for review — no implementation has started.**

> Two-layer reminder: this is the **ktayl-solution IS** (business context), not the RNCP cert (that's Retrieva).

## 1. Vision

A technical-underwriting **workbench** that is the single system of record for a commercial-lines risk
from broker submission to bind, with **auditable decisions**, **explainable pricing**, and one
**human-verified AI** assist (submission extraction). It binds into the live `ktayl-policy-service` and
publishes clean bound-risk events for reinsurance and actuarial downstream.

## 2. Personas (primary → supporting)

| Persona | Goal in the product | Key need |
|---|---|---|
| **Underwriter** (primary) | Assess vs appetite, price, quote, bind within authority | One file view; inline appetite + rating; fast quote |
| UW assistant/technician | Log submission, chase missing info, issue docs | Structured intake; extraction assist |
| Senior/technical UW | Approve referrals, own guidelines | (UW-03, deferred) referral triage + guideline authoring |
| UW manager | Portfolio steering, authority limits | Live pipeline / hit-ratio / rate-adequacy KPIs |
| Actuary/pricing | Own rate tables, watch rate adequacy | Versioned rate tables; premium explainability |
| Compliance | Sanctions/appetite screening on the risk | Screening gate + audit trail |

## 3. Functional requirements (by epic)

Requirements are stated as capabilities; the **v1 thin slice** (see Brief) implements the ⭐ items only.
Full story decomposition for the slice: `bmad/stories/underwriting/uw-v1-slice/`.

### UW-01 — Underwriting workbench (P1, the spine)
- ⭐ **FR-1.1** Create a structured **Submission** record per LOB (broker, insured, LOB, requested cover, dates, docs).
- ⭐ **FR-1.2** A **local entity model** for client/broker/insured (refactor to MDM later; do not block on MDM).
- ⭐ **FR-1.3** A single **underwriting file view** aggregating submission, exposure, guideline result, quote, decision.
- ⭐ **FR-1.4** **UW decision audit trail** — every accept/refer/decline/conditions records who, when, why (immutable, append-only).
- ⭐ **FR-1.5** **Bind → handoff** to `ktayl-policy-service` via a defined contract; publish a bound-risk event (NATS).
- FR-1.6 **Portfolio KPI view** (quote turnaround, hit ratio, straight-through rate, pipeline) — playbook §8.
- FR-1.7 **Authority matrix** enforcement → triggers referral (feeds UW-03 when built).

### UW-02 — Guidelines repository (P2)
- ⭐ **FR-2.1** **Versioned guideline** documents per LOB (prohibited risks, limits, exclusions), with change history + approval.
- ⭐ **FR-2.2** **Appetite/eligibility check** returning in-appetite / refer / decline **with a cited reason**, surfaced inline in UW-01.
- FR-2.3 RAG grounded guideline assist over the versioned corpus (limited-tier AI; citations required).

### UW-03 — Committee / escalation (P2, **deferred past v1**)
- FR-3.1 Escalation workflow for risks over authority limits (Temporal — SLA-tracked).
- FR-3.2 Committee decision recorded (approve/decline/conditions) fed back to the file + audit.

### UW-04 — Pricing / rating engine (P2)
- ⭐ **FR-4.1** **Versioned rate tables** per LOB (auditable like a control library), factor model → technical premium.
- ⭐ **FR-4.2** **Explainable premium breakdown** on the quote (base rate × factors + loadings/discounts with justification).
- FR-4.3 Rate-adequacy signal (technical vs charged premium) for the KPI view.

### UW-05 — Catastrophe / aggregate exposure (P3, **deferred past v1**)
- FR-5.1 Aggregate exposure by peril/zone; accumulation/scenario view feeding appetite limits.

## 4. Non-functional requirements (summary — full measurable set in the [NFR Register](./architecture/nfr-register.md))

| Category | Target |
|---|---|
| **Performance** | Workbench file view p95 < 1.5s; premium computation p95 < 800ms; extraction assist < 30s per submission |
| **Availability** | Business-hours SLO 99.5%; graceful degradation if the LLM/extraction path is down (manual entry always works) |
| **Scale (sim)** | Sized for a demo insurer: hundreds of open submissions, tens of concurrent underwriters |
| **Durability / DR** | Postgres = system of record; Velero backup; RPO ≤ 24h, RTO ≤ 4h (platform standard) |
| **Security** | Authentik SSO + MFA; per-role RBAC; secrets via ESO/Vault; default-deny NetworkPolicies; PII masking (Presidio) before any LLM call |
| **Observability** | RED metrics + traces (OTel→Tempo), logs (Loki), AI calls traced in Langfuse; the KPI view is product-level observability |
| **Explainability** | Every premium and every appetite decision is human- and auditor-legible (a hard requirement, not a nicety) |
| **Auditability** | Decision trail + rate/guideline versioning are immutable and queryable (ACPR expectation) |

## 5. Compliance & regulatory requirements (compliance-by-design — playbook §12)

Declared at design time, verified at the architecture + **security** gates. Insurer ≠ bank (no CRR/CRD/PSD2).

| Framework | Requirement on this product |
|---|---|
| **Solvency II** (spine) | Appetite/limit enforcement (UW-02), auditable rate tables (UW-04), clean exposure/bound-risk feed, decision audit trail |
| **IDD / DDA** | Product-governance checks, clear client info on the quote, complaints trail |
| **EU AI Act** | **Risk-tier every AI use case** (below); logging (Langfuse), human oversight, evaluation, incident mgmt |
| **GDPR** | Purpose limitation, minimisation, retention, **Presidio PII masking before LLM**, DPIA for any high-tier AI |
| **AML / Sanctions** | Sanctions + PEP screening gate **before bind**; TRACFIN-ready trail |
| **DORA / Outsourcing** | LLM provider + any SaaS = ICT third-party → in the ICT register (Retrieva), egress control, exit/BCP posture |

**AI-Act risk tiering (mandatory per use case):**

| AI use case | Tier | Controls |
|---|---|---|
| ⭐ Submission extraction (human-verified) | **limited** | logging, **human confirmation**, Presidio masking, provider in ICT register |
| Guideline check assist (RAG) | **limited** | citations, GDPR on corpus |
| Referral routing | **limited** | logging |
| AI Ops Copilot — proposes/acts on terms (parked) | **HIGH** | full: human oversight + contestability, DPIA, eval, monitoring, incident mgmt — **gated before any autonomous action** |

Evidence lands in the **Regulatory & Compliance #15** control library (`Risk→Control→Owner→Evidence→Testing→Finding→Remediation→Audit`).

## 5b. Technology stack (ADR-007)

Chosen per the org [stack-selection rule](https://github.com/andrelair-platform/minicloud-gitops/blob/main/.claude/rules/tech-stack-selection.md)
(best-fit per project, not a Go default): **Backend = Python 3.12 + FastAPI + Pydantic** (SQLAlchemy +
Alembic on Postgres; numpy/pandas for rate/pricing math; a Python extraction worker native to Docling/
LiteLLM). **Frontend = Next.js + React** (PWA only if a real mobile/offline need appears). Rationale + the
trade-off vs Java/Spring: [ADR-007](./architecture/adr/000-index.md#adr-007).

## 6. Cost

Reuses the existing self-hosted platform substrate (no new cloud spend). AI inference routes through the
existing **LiteLLM gateway** (department budget caps apply); extraction favours **local vLLM** where quality
allows, cloud fallback within budget. No third-party SaaS licences introduced in v1.

## 7. Dependencies

`ktayl-policy-service` (live bind target) · Distribution/CRM #13 (submission source) · Reinsurance #9 &
Data/Actuarial #5 (downstream consumers) · Compliance #15 (screening + control library) · MDM #20 (parked —
local entity model until a 2nd consumer). Platform substrate: Authentik, Postgres, NATS, Temporal, Docling/
markitdown, Qdrant/RAG, LiteLLM/vLLM, Langfuse. See [Solution Architecture](./architecture/solution-architecture.md).

## 8. Out of scope (v1)

AI Ops Copilot / autonomous action · standalone MDM · UW-03 committee workflow · UW-05 cat/aggregate ·
multi-LOB · broker self-service portal · reinsurance cession automation.

## 9. Definition of Done (product-level)

A submission for the v1 LOB (**Property**) can be taken **intake → appetite → rating → quote → bind** in the workbench,
**binds a real policy in `ktayl-policy-service`**, records an immutable decision with a cited appetite result
and an explainable premium, publishes a bound-risk event, and passes the **architecture + security** gates
with all v1 AI at limited tier and PII masked before any LLM call.

## References

[Brief](./brief.md) · [FDE Playbook](./fde-underwriting-playbook.md) · [Solution Architecture](./architecture/solution-architecture.md) · [NFR Register](./architecture/nfr-register.md) · [Threat Model](./architecture/threat-model.md) · [ADR index](./architecture/adr/000-index.md)
