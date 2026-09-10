---
id: UW-01
title: "EPIC: Underwriting workbench"
status: Ready
type: Epic
epic: underwriting
milestone: "UW — Underwriting v1"
estimate: 13
labels: [epic, insurance-lob, underwriting]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/ktayl-underwriting
project: 12
---

## Epic

Underwriting workbench.

## Why
The core UW flow: risk intake → assess against appetite/guidelines → price → quote → bind. The workbench an underwriter lives in.

## Scope (epic-level)
- [ ] Risk submission intake (data capture per LOB)
- [ ] Appetite + eligibility check; refer/decline/accept path
- [ ] Quote generation; bind to a policy (handoff to policy service)
- [ ] Referral to committee when limits exceeded (→ UW-03)
- [ ] Audit trail of UW decisions
