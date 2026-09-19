# Sprint Plan — Underwriting v1 (the thin slice)

> **BMAD artefact — SPRINT PLAN + READINESS GATE.** Decomposes the [Brief](./brief.md) thin slice into
> implementable stories with acceptance criteria, and states the readiness verdict.
> **Status: DRAFT for review.** These stories become `bmad/stories/underwriting/uw-v1-slice/` files
> (synced to **board #12**) **only after you approve this plan** — nothing is created on the board yet.

## Slice goal

One LOB (recommend **Property** or a **Financial Line**), one broker path, taken **submission → appetite
→ rating → quote → bind → audit**, binding a real policy in `ktayl-policy-service`. Defers UW-03 & UW-05.

## Story breakdown

Each story: parent epic · priority · estimate · acceptance criteria (happy + failure) · DoD.

### S001 — Structured submission intake + local entity model  · [UW-01] · P1 · 5
Capture a Submission (broker, insured, LOB, cover, dates, docs) against a **local entity model** (client/
broker/insured).
- **AC** ✓ create a submission for the chosen LOB; ✓ link/create local entities; ✓ persist to Postgres.
- **AC (fail)** ✗ incomplete submission is flagged "request-info", not silently accepted.
- **DoD** schema reviewed (ADR-002 interface seam for future MDM); unit + integration tests; no PII in logs.

### S002 — The underwriting file view  · [UW-01] · P1 · 5
A single pane aggregating submission + entities + guideline result + quote + decision.
- **AC** ✓ one screen shows the whole file; ✓ file view p95 < 1.5s (PERF-1).
- **DoD** RED metrics wired; task-inbox shape, not a CRUD form.

### S003 — UW decision audit trail (append-only)  · [UW-01] · P1 · 3
Record every accept/refer/decline/conditions with who/when/why.
- **AC** ✓ every decision is captured immutably; ✓ no destructive-update path (T2/AUD-1).
- **DoD** audit query demoed; append-only enforced at schema + code.

### S004 — Bind → `ktayl-policy-service` contract + bound-risk event  · [UW-01] · P1 · 8
Define and implement the bind handoff (ADR-006).
- **AC** ✓ accepting a quote binds a policy in `ktayl-policy-service`; ✓ authenticated + **idempotent** bind;
  ✓ a **NATS bound-risk event** is published.
- **AC (fail)** ✗ a duplicate bind does not create two policies (idempotency, T9); ✗ bind above authority is refused server-side (T7).
- **DoD** contract test against PAS; fault-injection retry test (AVL-3).

### S005 — Versioned guidelines + inline appetite check (cited)  · [UW-02] · P2 · 5
A small versioned guideline set for the LOB + an inline appetite/eligibility check.
- **AC** ✓ appetite check returns in-appetite / refer / decline **with a cited guideline reference** (EXP-2);
  ✓ guideline changes are versioned with author + approval (AUD-2).
- **DoD** citation stored on the decision; version history queryable.

### S006 — Versioned rate table + premium computation  · [UW-04] · P2 · 8
A couple of versioned rate tables for the LOB; factor model → technical premium.
- **AC** ✓ premium computed from base rate × factors; ✓ rate tables versioned/immutable (ADR-004);
  ✓ computation p95 < 800ms (PERF-2).
- **DoD** rate table change = new version; unit tests on factor math.

### S007 — Explainable premium breakdown on the quote  · [UW-04] · P2 · 3
- **AC** ✓ the quote shows base × each factor + loadings/discounts **with justification** (EXP-1).
- **DoD** breakdown stored + rendered; auditor-legible.

### S008 — Assisted submission extraction (human-verified)  · [UW-01 / AI, limited-tier] · P2 · 8
Docling/markitdown convert → **Presidio mask** → LiteLLM→vLLM extraction → **human verification** → populate S001's schema.
- **AC** ✓ extraction proposes structured fields; ✓ **nothing is persisted without human confirmation** (AI-1/ADR-003);
  ✓ **PII masked before the LLM call** (SEC-4/T4); ✓ async, UI never blocks (AVL-2); ✓ traced in Langfuse.
- **AC (fail)** ✗ a malicious document cannot trigger an action (prompt-injection T8 — extraction is data-only).
- **DoD** security-gate items (T4/T8) tested; extraction logs + human sign-off in the audit trail.

**Slice total ≈ 45 pts.** Sequence: S001→S002→S003 (the file), S005+S006+S007 (appetite+pricing),
**S004 (bind — the proof)**, then S008 (the AI leverage) last within the slice.

## Sprint-planning readiness gate

| Check | Verdict |
|---|---|
| Business need grounded (real process/user/outcome) | ✅ FDE playbook §2–3, §6, §8 |
| Product contract defined (PRD, NFRs, compliance) | ✅ [PRD](./prd.md) + [NFR register](./architecture/nfr-register.md) |
| Architecture spine + C4 + ADRs | ✅ [Solution Architecture](./architecture/solution-architecture.md) + [ADRs](./architecture/adr/000-index.md) |
| Threat model / security controls declared | ✅ [Threat Model](./architecture/threat-model.md) (T4/T8 = security-gate blockers) |
| Scope disciplined (thin slice, deferrals explicit) | ✅ one LOB, UW-03/UW-05 deferred, copilot parked |
| Dependencies are contracts, not blockers | ✅ PAS contract early; MDM local-first; NATS events |
| **Open decisions for the owner** | ⚠️ **(1)** pick the v1 LOB (Property vs a Financial Line); **(2)** confirm the `ktayl-policy-service` bind API shape |

**Verdict: CONCERNS → PASS on two owner decisions.** The plan is implementation-ready once you (1) choose
the v1 LOB and (2) confirm the bind contract shape with the policy service. No code should start before that.

## After approval
1. You review + approve this plan and the [PRD](./prd.md) / [architecture](./architecture/solution-architecture.md).
2. Story files are written to `bmad/stories/underwriting/uw-v1-slice/` (S001–S008) and sync to **board #12**.
3. Implementation begins per the sequence above — thin slice first, security gate (T4/T8) enforced.
