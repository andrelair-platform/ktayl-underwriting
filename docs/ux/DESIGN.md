# DESIGN — Underwriter Workbench (#12)

> **BMAD/SA artefact (UX design).** The visual + interaction design of the Next.js workbench. Companion:
> [EXPERIENCE.md](./EXPERIENCE.md) (journeys). Reflects what is **built + live on dev**
> (`underwriting-app.10.0.0.200.nip.io`). Owner = UX/UI + TL.

## 1. Design intent

The workbench is an **AI-native task inbox**, not a CRUD admin. The appetite engine auto-decides the rule
(accept / decline); the human's scarce attention goes to the **referrals** and to the accept→quote→bind
judgement. So the design optimises for **triage speed and explainability**, not data entry: every screen
answers "what needs me, and why?" before "edit these fields".

## 2. Design language

- **Framework:** Next.js 16 (App Router) + React 19, **Tailwind v4** utility CSS. No component library —
  a small hand-built set (badges, cards, tables) keeps the bundle lean and the look intentional.
- **Palette:** neutral slate canvas (`#f6f7f9`), near-black text, a single **indigo** accent for primary
  actions and identity. Semantic status colours are reserved for the decision outcomes only (below), so
  colour always *means* something.
- **Typography:** system UI sans stack; `tabular-nums` for money and counts so columns align.
- **Density:** comfortable tables + cards on a max-6xl centered column; generous whitespace over chrome.

## 3. The status vocabulary (one component, everywhere)

`OutcomeBadge` is the single source of visual truth for a submission's state — used identically in the
inbox and the detail header, so the same state always looks the same:

| State | Colour | Meaning |
|---|---|---|
| **Accept** | green | within appetite |
| **Refer** | amber | needs an underwriter (the inbox's reason to exist) |
| **Decline** | red | out of appetite |
| **Unassessed** | slate | intake done, not yet assessed |
| **Bound** | indigo | policy created in the PAS — terminal, frozen |

`bound` takes visual precedence over the appetite outcome (a bound accept shows **Bound**), because "is
this still actionable?" is the first question in triage.

## 4. Screens

### 4.1 Inbox (`/`) — the default surface
- A header stating the operating principle ("the system auto-decides the rule; work the **referrals**").
- **Outcome tabs** — All · Referrals · Accepted · Declined (links to `/?outcome=refer` etc.) → the
  server re-queries `GET /v1/submissions?outcome=`; the whole page is server-rendered, no client fetch.
- A **table**: Status badge · line of business · TIV (right-aligned, `tabular-nums`) · risk location ·
  cover · created. Whole rows link to the detail.
- **States:** empty ("No submissions here yet — Create one"), and a red error card if the API is
  unreachable (the BFF surfaces the real status/detail, never a blank page).

### 4.2 Submission detail (`/submissions/[id]`)
- Header: id (mono) + the status badge.
- An **action bar** (assess / rate & quote / bind) whose buttons enable/disable from the live state
  (can't quote a decline; can't bind without an accepted quote; a **bound** submission shows a "frozen"
  note and hides the mutating actions).
- Four cards: **Risk** (the facts), **Appetite decision** (outcome + ruleset version + reason-code
  chips), **Rating & quote** (the premium + the **explainable breakdown** table — each line item's
  label/kind/value and running subtotal, reconciling to the premium), **Policy binding** (policy number,
  PAS id, bound-risk event status). Below: the **audit trail** (append-only, timestamped).
- **States:** missing id → a dedicated 404 page; each card has its own "not yet" empty state.

### 4.3 New submission (`/submissions/new`)
- A single grouped form (counterparty / risk) → a **server action** creates the submission and redirects
  to its detail. Money is entered in **euros** and converted to eurocents at the boundary. Inline error
  banner on validation/API failure.

## 5. Interaction principles

- **Reads are instant + always live** (`cache: no-store`); **writes are server actions** with an inline
  pending state on the triggering button and `revalidatePath` so the page reflects the new state without a
  manual refresh.
- **No destructive action without state guards** — the UI mirrors the backend's invariants (bound = frozen,
  decline = unquotable) so an underwriter can't attempt an impossible transition.
- **Explainability is first-class** — the rating breakdown and the reason codes are shown, not hidden
  behind a tooltip (Solvency II / ACPR auditability, NFR-EXP).

## 6. Accessibility & responsive (baseline)

Semantic HTML (`<table>`, `<dl>`, `<form>`, labelled inputs), colour never the sole signal (every badge
carries a text label), keyboard-navigable links/buttons. Layout reflows on the 6xl→mobile range. A full
RGAA pass is out of scope for this internal tool (cf. Retrieva, which owns the accessibility cert evidence).
