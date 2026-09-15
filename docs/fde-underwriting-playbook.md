# FDE Playbook — Underwriting & Pricing (ktayl-solution IS)

> **What this is.** A Forward-Deployed-Engineer field guide to ktayl's **underwriting (UW) & pricing**
> domain: how the business actually works, where the pain is, and where software + AI deliver
> measurable value. It is the **discovery layer** that sits *under* the epic backlog
> (`UW-01 … UW-05`) — read this before building, so every story is justified by a real process, a
> real user, and a measurable outcome, not "where can we put a chatbot?"

> **Two-layer reminder.** This is the **ktayl-solution insurance IS** (the business/org context). It is
> **not** the RNCP certification — that is **Retrieva**, a separate product. Nothing here concerns Retrieva.

**Reference model:** ktayl is a **commercial-lines / large-risk IARD** insurer. Underwriting here means
**technical underwriting of complex business risks** (Marine,
Engineering, Property, Financial Lines, International Programs) — *not* mass-market personal-lines
auto/home, where the flow is far more automated. The complexity is the point: large risks are
judgement-heavy, document-heavy, and referral-heavy, which is exactly where an FDE finds leverage.

**Where UW sits in the value chain:**

```
DISTRIBUTION / CRM  ─►  UNDERWRITING & PRICING  ─►  POLICY ADMIN (PAS)  ─►  CLAIMS
  broker submission        (this domain)              bind → contract         FNOL → …
                                 │
                                 ├─► REINSURANCE      (cessions on bound risk)
                                 └─► DATA / ACTUARIAL (rate tables, exposure, loss feedback)
```

See the [EA Blueprint](https://andrelair-platform.github.io/minicloud-platform-docs/insurance-platform/enterprise-architecture-blueprint)
for the full 12-domain map. Underwriting = **domains #2 (workbench) + #3 (pricing)**, board **#12**.

---

## 1. How to use this playbook

The FDE method, applied per pain point:

```
business process → pain point → data / documents → existing systems
    → decision / task → automation opportunity → AI capability → measurable outcome
```

Every AI/automation idea in §7 is traced through this chain. If a step in the chain is missing (no
data, no measurable outcome, no real decision), the idea is not ready — that is the discipline.

**Build-order discipline (decided 2026-09-14):** *business tools first; the AI/automation layer last.*
The **AI Ops Copilot** is the **capstone** — it automates *over* systems, so it only pays off once the
workbench, guidelines and pricing engine exist. §7 therefore splits opportunities into **(a) build now,
inside the workbench** and **(b) parked capstone** — do not invert this.

**The "don't rebuild Open WebUI" test.** Grounded Q&A over documents (guidelines, wordings, past
submissions) is **Open WebUI + curated content — config, not code**. Only build custom AI for what OWUI
*cannot* do: **structured decisions, authorized actions into ktayl systems, multi-step workflows.**

---

## 2. Actors — who lives in underwriting

| Role | What they do | Where they feel pain |
|---|---|---|
| **Broker** (external) | Sends the submission (risk data + docs), negotiates terms | Slow quotes, opaque decline reasons, re-keying the same data per insurer |
| **UW Assistant / Technician** | Logs the submission, chases missing info, sets up the file, issues docs | Manual data entry from PDF/email; chasing incomplete submissions |
| **Underwriter** (line UW) | Assesses risk vs appetite, prices, sets terms, quotes, binds within authority | Fragmented data; manual appetite/limit checks; spreadsheet rating; no single file view |
| **Senior / Technical Underwriter** | Handles complex risks, approves referrals, owns guidelines | Referral triage overhead; inconsistent decisions across the team |
| **UW Manager / Line Manager** | Portfolio steering, authority limits, performance | No live view of pipeline, hit ratio, rate adequacy, referral load |
| **Actuary / Pricing** | Owns rate tables, monitors rate adequacy vs loss experience | Rate tables in spreadsheets; slow feedback loop from claims |
| **Cat Modeller / Exposure Mgr** | Aggregate & nat-cat accumulation, appetite by zone/peril | Aggregates recomputed manually; late warning on limit breaches |
| **Technical UW Committee** | Reviews risks over authority limits | Ad-hoc scheduling; decisions not captured against the file |
| **Compliance / Legal** | Sanctions/appetite/regulatory checks on the risk | Manual screening; audit trail scattered across email |
| **Reinsurance** (downstream) | Cedes bound risk to treaty/fac | Needs clean bound-risk data; often re-keyed |

**Primary user of the product = the Underwriter.** UW-01 (the workbench) is "the screen the
underwriter lives in." Everyone else is a supporting actor whose work feeds or consumes that file.

---

## 3. The end-to-end underwriting process (as-is → target)

The core flow (new business), with mid-term and renewal variants after it.

### 3.1 New business — submission to bind

| # | Stage | What happens | Decision / output |
|---|---|---|---|
| 1 | **Submission intake** | Broker sends risk data + documents (email, PDF, spreadsheet, submission pack) | A structured *submission* record per LOB |
| 2 | **Triage / completeness** | Is the data complete? In-appetite at first glance? Worth quoting? | Accept-to-quote / request-info / quick-decline |
| 3 | **Appetite & eligibility** | Check against **underwriting guidelines** (prohibited risks, limits, exclusions per LOB) | In-appetite / refer / decline (with reason) |
| 4 | **Risk assessment** | Analyse exposure, loss history, risk-engineering reports; site/COPE data for property | A risk quality view + open questions |
| 5 | **Pricing / rating** | Apply rating factors + rate tables → technical premium; loadings/discounts with justification | An explainable premium + terms |
| 6 | **Aggregate / cat check** | Does binding this breach an aggregate/nat-cat limit by peril/zone? | Within-appetite / refer to exposure mgr |
| 7 | **Terms & quote** | Assemble limits, deductibles, conditions, wording; produce the quote | A quote issued to the broker |
| 8 | **Referral / committee** | If over authority or complex → escalate | Committee decision (approve/decline/conditions) with SLA |
| 9 | **Negotiation** | Broker negotiates terms/price; iterate | Revised quote(s) |
| 10 | **Bind** | Accept → bind the risk | **Handoff to Policy Admin (PAS)** to issue the contract |
| 11 | **Post-bind** | Feed reinsurance cessions; feed exposure/aggregate; audit trail closed | Clean bound-risk record downstream |

### 3.2 Variants

- **Renewal** — same flow, pre-populated from the expiring policy (PAS) + updated exposure/loss;
  the decision is *re-underwrite / re-price / non-renew*. Highest volume, most automatable.
- **Mid-term endorsement** — a change to a bound risk (added location, increased limit) → re-assess
  appetite/aggregate + re-price the delta → PAS endorsement. (Policy Admin owns the endorsement;
  UW owns the *re-assessment*.)

### 3.3 What breaks today (the as-is reality)

The submission arrives as **unstructured documents** (email + PDF + broker spreadsheet). Everything
downstream is manual: re-keying data, eyeballing guidelines, rating in Excel, recomputing aggregates,
and a decision trail spread across inboxes. **There is no single underwriting file** — that absence is
the root pain the workbench (UW-01) fixes.

---

## 4. Data objects (the domain model, business-first)

The nouns the workbench manages. These become the schema (BE/DBA) and the **MDM dependency** (client,
broker, insured entity are *shared* master data — see §9).

| Object | Key attributes | Owner / source | Notes |
|---|---|---|---|
| **Submission** | broker, insured, LOB, requested cover, dates, docs | Distribution / broker | The intake unit; starts unstructured |
| **Risk / Insured** | legal entity, sector, geography, COPE/exposure data | **MDM** (shared) | Reused across quotes, claims, reinsurance |
| **Exposure** | TIV/limits by location, peril, zone | Submission + risk-eng | Feeds aggregate (UW-05) |
| **Underwriting guideline** | LOB rules, prohibited risks, limits, exclusions | Technical UW | Versioned, auditable (UW-02) |
| **Rate table** | rating factors → base rates, per LOB | Actuary/Pricing | Versioned like a control library (UW-04) |
| **Quote** | terms, limits, deductibles, premium breakdown, wording | Underwriter | Explainable premium (UW-04) |
| **Referral** | trigger, authority breached, target committee | Workbench → committee | SLA-tracked (UW-03) |
| **UW Decision** | accept/refer/decline/conditions + reason + author + timestamp | Underwriter/committee | The **audit trail** (UW-01/03) |
| **Aggregate / accumulation** | exposure sum by peril/zone vs appetite limit | Exposure mgr | Scenario view (UW-05) |
| **Authority matrix** | who can bind what, by LOB/limit | UW management | Drives referral triggers |

---

## 5. Systems — as-is vs target

| Capability | As-is (the pain) | Target system | Epic |
|---|---|---|---|
| A single underwriting file | Email + shared drive + Excel; no system of record | **UW workbench** | **UW-01** |
| Appetite / guideline check | Underwriter's memory + PDF guideline docs | **Versioned guidelines repo**, queryable inline | **UW-02** |
| Escalation of large/complex risks | Ad-hoc email + calendar | **Committee / escalation workflow** with SLA | **UW-03** |
| Technical pricing | Spreadsheet rating, hand-applied loadings | **Rating engine** w/ versioned rate tables + explainable premium | **UW-04** |
| Aggregate / nat-cat exposure | Manual spreadsheet recompute | **Aggregate exposure / cat view** feeding appetite | **UW-05** |
| Contract issuance | (downstream) | **Policy Admin service** (`ktayl-policy-service`, already live) | handoff |

**Platform substrate already available** (from the EA Blueprint deployed reality — use it, don't
rebuild it): Authentik SSO, Postgres (per-service), NATS (events), Temporal (workflow — good fit for
UW-03 escalation SLAs), n8n (integration), Docling + markitdown (document conversion/OCR — the
submission-intake enabler), Qdrant + RAG (grounded search), LiteLLM + vLLM (LLM serving), Langfuse
(AI observability). **`ktayl-policy-service` is the live bind target.**

---

## 6. Pain points → manual tasks (ranked by leverage)

| # | Pain point | Manual task today | Leverage |
|---|---|---|---|
| P1 | **Submission is unstructured** | Re-key risk data from PDF/email/spreadsheet into a file | 🔴 highest — blocks everything, high volume |
| P2 | **No single UW file** | Hunt across inbox/drive to assemble context | 🔴 |
| P3 | **Appetite/guideline check is manual & inconsistent** | Recall or look up PDF rules per risk | 🟠 |
| P4 | **Rating in spreadsheets** | Hand-build premium, error-prone, not explainable | 🟠 |
| P5 | **Aggregates recomputed by hand** | Late/absent warning on limit breaches | 🟠 |
| P6 | **Referrals are ad-hoc** | Email chains, no SLA, decisions lost | 🟡 |
| P7 | **No portfolio view** | Manager can't see pipeline/hit-ratio/rate-adequacy live | 🟡 |
| P8 | **Renewal re-underwriting from scratch** | Re-key the expiring risk | 🟠 — high volume, very automatable |

---

## 7. AI / automation opportunities

Each traced through the FDE chain. **Split by build-order:** (a) build now (thin AI *inside* the
business tools) vs (b) parked capstone (the AI Ops Copilot). Grounded doc-Q&A is called out as
**OWUI, not code**.

### 7a. Build now — thin AI capabilities *inside* the workbench

| Opportunity | FDE chain | AI capability | Measurable outcome |
|---|---|---|---|
| **Submission extraction (P1)** | unstructured submission → re-keying → PDF/email/spreadsheet → *(no system)* → "populate the UW file" → **document extraction** → structured submission | Docling/markitdown OCR + an LLM extraction pass (LiteLLM→vLLM) mapping to the submission schema, **human-verified** | ↓ intake time per submission (e.g. 20 min → 3 min); ↑ % submissions quoted |
| **Guideline check assist (P3)** | appetite check → manual lookup → guideline docs → "in-appetite?" → **grounded retrieval** over UW-02 | RAG over the versioned guidelines repo, cited, surfaced inline in UW-01 | ↓ decision variance; faster refer/decline with a cited reason |
| **Renewal pre-fill (P8)** | renewal → re-key expiring risk → PAS + last exposure → "re-underwrite" → **summarisation/diff** | LLM summary of the expiring file + change highlights, human-confirmed | ↓ renewal handling time; ↑ renewal throughput |
| **Referral routing (P6)** | referral → manual triage → authority matrix → "who decides?" → **classification** | Rule + light-model routing to the right committee/authority | ↓ referral turnaround; every decision captured |

> **OWUI, not code:** "Ask the guidelines / past wordings / prior submissions" as a chat is **Open
> WebUI + curated content**. Build the *inline, in-workbench, structured* version (above) only where the
> answer must land **in the file with an action**, which OWUI cannot do.

### 7b. Parked capstone — the AI Ops Copilot (do **not** build yet)

Once UW-01…05 exist and hold real data, the **AI Ops Copilot** (board #19, **parked**) becomes the
capstone: it *makes and executes* validated, audited UW actions — e.g. draft a full quote from a
submission, propose terms within appetite, and (on human approval) **write** the referral/decision back
into the workbench and hand off to PAS. This is a **structured-decision + authorized-action + multi-step
workflow** system — exactly the class OWUI cannot do — but it has **nothing to automate until the
business tools are built.** Keep the brief; build last. See
[build-sequencing decision](https://andrelair-platform.github.io/minicloud-platform-docs/insurance-platform/enterprise-architecture-blueprint).

---

## 8. KPIs — how underwriting is measured (and what the product must expose)

| KPI | Definition | Why it matters | Where it comes from |
|---|---|---|---|
| **Quote turnaround time** | submission → quote issued | Broker service / hit ratio driver | Workbench timestamps |
| **Hit ratio (bind:quote)** | bound ÷ quoted | Competitiveness & appetite fit | Workbench |
| **Quote:submission ratio** | quoted ÷ received | Triage efficiency | Workbench |
| **Referral rate** | % risks referred | Authority calibration / bottleneck signal | UW-03 |
| **Straight-through rate** | % bound without referral/manual rework | Automation payoff | Workbench |
| **Rate adequacy** | technical vs charged premium | Profitability | UW-04 + actuarial |
| **Loss ratio (feedback)** | claims ÷ premium by segment | Closes the pricing loop | Claims/Data (downstream) |
| **Aggregate utilisation** | exposure vs appetite limit by peril/zone | Solvency / cat risk | UW-05 |
| **Pipeline value / mix** | open submissions by LOB/stage | Portfolio steering | Workbench |

The **portfolio view (P7)** = these KPIs, live — a UW-01/UW management deliverable, and the honest
"measurable outcome" for every §7 automation.

---

## 9. Dependencies & cross-domain contracts

- **MDM (master data) — dependency, not a blocker.** *Client, broker, insured entity* are **shared
  master data**. Per the build-order decision, **MDM (#20) is parked** and *emerges as this domain needs
  shared entities* — so UW-01 starts with a **local entity model** and refactors to MDM when a second
  consumer exists. Do **not** block UW-01 on standing up MDM first.
- **Policy Admin (`ktayl-policy-service`, live)** — the **bind handoff** target. Define the bind → policy
  contract early (UW-01 ↔ PAS).
- **Distribution / CRM (#13)** — the **submission source**. Until a broker portal exists, intake is
  document-based (that is what P1's extraction addresses).
- **Reinsurance (#9)** & **Data/Actuarial (#5)** — downstream consumers of bound-risk + exposure;
  keep the bound-risk record clean and event-published (NATS).
- **Compliance (#15)** — sanctions/appetite screening on the risk; capture in the decision audit trail.

---

## 10. Recommended thin slice (the first thing to build)

Standing up Underwriting means **one narrow end-to-end flow that actually binds**, not 5 half-built
epics. Recommended v1 slice (crosses the fewest boundaries, proves the file):

```
Submission intake (structured, + assisted extraction for one LOB)
   → appetite/eligibility check against a small versioned guideline set (UW-02 slice)
   → simple rating for that LOB (UW-04 slice, a couple of rate tables)
   → quote
   → bind → handoff to ktayl-policy-service
   → UW decision audit trail
```

Pick **one LOB** (e.g. Property or a Financial Line) and **one broker path**. This exercises UW-01's
spine + thin slices of UW-02 and UW-04, defers UW-03/UW-05 until volume justifies them, and produces a
real, demoable bind. The §7a extraction assist is the highest-leverage AI to add *within* this slice;
the §7b copilot stays parked.

> Full story authoring goes through **BMAD** (`/bmad-spec` per epic → `/bmad-create-epics-and-stories`
> → `/bmad-sprint-planning`), grounded in this playbook. Governance: this is a **Path C** new-domain
> build → the architecture + security review gates apply (see `bmad-compliance.md`).

---

## 11. Governance & compliance notes (light)

- **Delegated authority** — the authority matrix drives referral triggers (UW-03); enforce it in the
  workbench, don't rely on discipline.
- **Auditability** — every UW decision (accept/refer/decline/conditions) records *who, when, why*. This
  is both good UW practice and regulatory expectation (ACPR); the rate table + guideline **versioning**
  is the same auditability applied to pricing/rules.
- **DORA context** — this is org-level operational resilience of a business system; the certification
  DORA product is **Retrieva** (separate). Don't conflate.
- **Explainability** — the premium breakdown (UW-04) and the cited guideline decision (UW-02) exist so a
  human (and an auditor) can see *why* — a prerequisite before any §7b copilot is allowed to act.

---

## References

- [EA Blueprint — the 12-domain insurer IS](https://andrelair-platform.github.io/minicloud-platform-docs/insurance-platform/enterprise-architecture-blueprint)
- [Business Applications Catalog](https://andrelair-platform.github.io/minicloud-platform-docs/insurance-platform/business-applications-catalog)
- Epic backlog: `bmad/stories/underwriting/` (UW-01 … UW-05) · Board **#12**
- Bind target: `ktayl-policy-service` (Policy Admin, live)
