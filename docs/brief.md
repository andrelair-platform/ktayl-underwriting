# Product Brief — Underwriting & Pricing (ktayl-underwriting, board #12)

> **BMAD artefact — DISCOVERY.** The business framing that sits above the PRD. Grounded in the
> [FDE Underwriting Playbook](./fde-underwriting-playbook.md) (the discovery layer) and the
> [EA Blueprint](https://andrelair-platform.github.io/minicloud-platform-docs/insurance-platform/enterprise-architecture-blueprint).
> **Status: DRAFT for review — no implementation has started.**

> **Two-layer reminder.** This is the **ktayl-solution insurance IS** (the org/business context), **not**
> the RNCP certification. The certification product is **Retrieva** (separate). Nothing here is cert evidence.

## The problem

ktayl is a **commercial-lines / large-risk IARD** insurer. Technical underwriting of complex business
risks (Marine, Engineering, Property, Financial Lines, International) is judgement-, document- and
referral-heavy. Today the submission arrives as **unstructured documents** (email + PDF + broker
spreadsheet) and **there is no single underwriting file**: risk data is re-keyed, guidelines are
recalled from memory or PDFs, pricing is done in spreadsheets, aggregates are recomputed by hand, and
the decision trail is scattered across inboxes. That missing system-of-record is the root pain.

## Who it's for

**Primary user: the Underwriter** — "the screen the underwriter lives in." Supporting actors whose work
feeds or consumes the file: UW assistant/technician, senior/technical UW, UW manager, actuary/pricing,
cat modeller, technical committee, compliance, and (downstream) reinsurance. Full actor map: playbook §2.

## Why now

The **Policy Admin service (`ktayl-policy-service`) is already live** — it is the bind target waiting for
a real upstream. Underwriting is the **highest-value** next domain: it feeds the live PAS, and the FDE
discovery playbook is already written. Building it makes the policy-admin investment pay off end-to-end.

## Goals (v1)

1. Give the underwriter a **single underwriting file** — one system of record for a submission from
   intake to bind, replacing inbox+drive+Excel.
2. Prove **one narrow end-to-end flow that actually binds** (not five half-built epics) — submission →
   appetite check → rating → quote → **bind → handoff to `ktayl-policy-service`** → decision audit trail.
3. Make the two regulated primitives **auditable and versioned from day one**: the **UW decision trail**
   (who/when/why) and the **rate tables + guidelines** (versioned like a control library).
4. Add the **single highest-leverage AI capability** *inside* the workbench — human-verified **submission
   extraction** — and nothing more (the AI Ops Copilot stays parked).

## Non-goals (v1) — deliberate, not gaps

- **No AI Ops Copilot / autonomous action** (board #19, parked). AI is assistive + human-verified only;
  no §7b high-tier AI until the business tools hold real data and the high-risk AI-Act controls are in place.
- **No standalone MDM** (#20 parked). UW-01 starts with a **local entity model** and refactors to MDM when
  a second consumer exists — do not block on MDM.
- **Defer UW-03 (committee/escalation) and UW-05 (cat/aggregate)** until volume justifies them. v1 is one
  LOB, one broker path.
- **Not** rebuilding grounded doc-Q&A — "ask the guidelines/wordings" is **Open WebUI + curated content**,
  config not code. Custom build only for structured, in-file, actioned decisions.

## The thin slice (first thing to build) — playbook §10

```
Submission intake (structured, + human-verified extraction for ONE LOB)
   → appetite/eligibility check against a small versioned guideline set (UW-02 slice)
   → simple rating for that LOB (UW-04 slice — a couple of rate tables, explainable premium)
   → quote
   → bind → handoff to ktayl-policy-service
   → UW decision audit trail
```

**v1 LOB = Property** (chosen) with **one broker path**. Exercises the UW-01 spine + thin slices of UW-02
and UW-04; defers UW-03/UW-05; produces a real, demoable bind. Property gives the richest COPE/exposure data
to exercise the file + rating and is the best fit for the extraction assist.

## Success metrics (the honest "measurable outcome")

| Metric | v1 target signal |
|---|---|
| A submission can be taken **intake → bind** in one system | end-to-end demo binds a policy in `ktayl-policy-service` |
| **Submission intake time** (with extraction assist) | e.g. ~20 min → ~3 min per submission, human-verified |
| **Every UW decision** recorded who/when/why | 100% of accept/refer/decline captured in the audit trail |
| **Explainable premium** | every quote carries a rate-factor breakdown |
| **Quote turnaround time** exposed | live workbench KPI (playbook §8) |

## Scope boundary & dependencies (contracts, not blockers)

- **`ktayl-policy-service` (live)** — define the **bind → policy contract** early (UW-01 ↔ PAS).
- **Distribution/CRM #13** — submission source; until a broker portal exists, intake is document-based
  (that is what the extraction assist addresses).
- **Reinsurance #9 / Data-Actuarial #5** — downstream consumers; keep the bound-risk record clean and
  **event-published (NATS)**.
- **Compliance #15** — sanctions/appetite screening captured in the decision trail; evidence lands in the
  #15 control library.

## Governance path

This is a **Path C** new-domain build → the **architecture spine review + security review gates** apply
(`bmad-compliance.md`). The regulatory obligations (Solvency II, IDD, EU AI Act, GDPR, AML, DORA) are
declared at design time — see the [PRD](./prd.md) §Compliance and the playbook §12.

## References

- [FDE Underwriting Playbook](./fde-underwriting-playbook.md) — the discovery layer under this brief
- [PRD](./prd.md) · [Solution Architecture](./architecture/solution-architecture.md)
- Epics: `bmad/stories/underwriting/` (UW-01…UW-05) · Board **#12** · Bind target: `ktayl-policy-service`
