---
id: UW-04-S02
title: "Pricing P1 — technical vs commercial premium separation + quote manifest"
status: Done
type: Story
epic: underwriting
milestone: "UW — Underwriting v1"
estimate: 5
labels: [underwriting, pricing, python, backend]
priority: P2
assignee: AndreLiar
repo: andrelair-platform/ktayl-underwriting
project: 12
initiative: Insurance LOB
---

## Story
As an actuary/underwriter, I want the premium build-up to separate the **technical** premium from the
**commercial** premium (and show taxes/fees), so a quote is actuarially legible and defensible — the
first step of the ADR-009 pricing evolution, pure-engine, **no ML**.

## Scope (ADR-009 P1)
Restructure the deterministic `rate()` build-up into the staged chain, each step a `LineItem` tagged by
stage, and persist the fuller **quote manifest** (subtotals + input facts), without touching the pure
`rate()` seam's contract shape.

```
LOSS COST (pure premium)   base ‰ × TIV × occupancy × risk adjustments (high_tiv / sprinklered)
+ technical loadings        expense loading · risk/capital margin · CAT provision
= TECHNICAL PREMIUM
× commercial adjustment     bounded, default neutral (1.0); out-of-band → RatingError (referral)
= COMMERCIAL PREMIUM
+ taxes/fees                policy fee + IPT (jurisdiction rate)
= FINAL QUOTED PREMIUM
```

## Acceptance criteria
- [x] AC-1: `rate()` stays **pure** (no I/O) and **backward-compatible** — a rate table with no loading
  params (v1) produces the identical breakdown + premium as today (neutral stages emit no line items).
- [x] AC-2: each `LineItem` carries a `stage` (`loss_cost` / `technical` / `commercial` / `taxes`); the
  breakdown exposes `pure_premium_minor`, `technical_premium_minor`, `commercial_premium_minor`,
  `taxes_minor`, `premium_minor`; the last line item reconciles to `premium_minor`.
- [x] AC-3: money stays eurocents, high-precision `Decimal`, **rounded once** at the end; IPT computed on
  the commercial premium; fees additive.
- [x] AC-4: a **v2 rate table** (seeded, immutable) carries the loading stack (expense/risk/CAT/IPT/fees +
  commercial-adjustment bounds); `current()` → v2.
- [x] AC-5: the **quote manifest** is persisted — `Quote` gains the stage subtotals + the input `facts`
  (replayable); the API exposes them.
- [x] AC-6: a commercial adjustment outside the rate-table bounds raises `RatingError` (→ referral), not a bad price.
- [x] AC-7: L1 unit tests for every stage + reconciliation; existing rating tests still pass; coverage ≥ 70%.

## DoD
Pure-engine P1 shipped on dev, full L1 green, as-built note in the ADR/solution-architecture, story Done.
Later phases (P2 LLM extraction, P3 GLMs) build on this staged seam — not in scope here.
