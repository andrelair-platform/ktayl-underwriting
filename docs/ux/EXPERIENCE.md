# EXPERIENCE — Underwriter Workbench (#12)

> **BMAD/SA artefact (UX experience).** The user journeys + information architecture of the workbench.
> Companion: [DESIGN.md](./DESIGN.md) (visual/interaction). Reflects what is **built + live on dev**.

## 1. Personas

| Persona | Goal | What the workbench gives them |
|---|---|---|
| **Underwriter** (primary) | Clear the queue of risks that need judgement; price + bind the good ones | A referral-first inbox → a one-screen submission file with the decision, the explainable price, and the bind action |
| **Underwriting manager** (secondary) | See what's flowing / stuck | The inbox filtered by outcome; (KPI view = future) |
| **Compliance / auditor** (occasional) | Reconstruct *why* a risk was accepted/priced/bound | The append-only audit trail + reason codes + versioned rating breakdown on every submission |

## 2. The core principle (why this shape)

> **The system automates the rule; the human works the exception.**

The appetite engine assesses every submission to accept / refer / decline deterministically. An
underwriter should **not** re-read the ones the system can decide — their attention is the scarce
resource. So the primary journey is **triage the referrals**, and everything else (accepted risks to
price, the full history) is one filter-tab away. This is the AI-native "task inbox" pattern, not a
records browser.

## 3. Primary journey — work a referral

```
Inbox (Referrals tab)                → the queue that needs a human
  → open a referred submission        → the one-screen file
    → read: risk facts, WHY it referred (reason codes), the appetite outcome
    → Rate & quote                    → see the explainable premium build-up
    → (judgement) Bind to policy      → policy created + activated in the live PAS, bound-risk event emitted
  → back to the inbox                 → the item now shows "Bound" (frozen)
```

Every step is on **one or two screens**; the underwriter never assembles context from multiple systems —
the file already carries the decision, the price rationale, the binding state, and the audit trail.

## 4. Secondary journeys

- **Intake a new submission** — New submission form → created → lands on its detail, ready to assess.
- **Price an accepted risk** — Accepted tab → open → Rate & quote → (optionally) Bind.
- **Audit a decision** — open any submission → the appetite reason codes + the versioned rating breakdown
  + the append-only audit trail answer "why" without leaving the file.
- **Handle the unhappy path** — a declined risk is visibly unquotable; a bound risk is visibly frozen;
  an API outage shows an explicit error, not a blank screen.

## 5. Information architecture

```
/                         Inbox (default)  — tabs: All · Referrals · Accepted · Declined
/submissions/new          Intake form
/submissions/{id}         Submission file  — Risk · Appetite decision · Rating & quote · Binding · Audit
```

Flat and shallow by design: two clicks from "what needs me" to "acted on it". No nested navigation, no
dashboards-of-dashboards.

## 6. State → action mapping (what the user can do, when)

| Submission state | Available actions | Rationale |
|---|---|---|
| Unassessed | Assess | can't price/bind an un-assessed risk |
| Assessed = decline | (none — read only) | out of appetite; not quotable |
| Assessed = refer/accept, no quote | Assess (re-run), Rate & quote | referrals are quotable pending judgement |
| Quoted, accepted | Bind | only an accepted, quoted risk binds |
| Bound | (none — frozen) | terminal; the record is locked (backend M1 invariant) |

The UI never offers an action the backend would reject — the experience of "the button isn't there"
replaces the experience of "the action failed".

## 7. Deferred experience (design recorded, not built)

- **AI submission extraction** — a broker document → a pre-filled, **human-verified** intake (ADR-003;
  extraction proposes, the underwriter confirms; nothing persists unconfirmed).
- **KPI / portfolio view** for the manager persona.
- **Referral committee / SLA** escalation (UW-03, Temporal — ADR-005).
- **Authentik SSO** on the workbench ingress + per-scope authz (the documented prod-onboarding gate;
  dev runs open).
