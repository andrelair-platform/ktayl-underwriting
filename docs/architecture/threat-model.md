# Threat Model — Underwriting & Pricing (#12)

> **BMAD/SA artefact — STRIDE-lite.** Trust boundaries, attack surface, and controls for the underwriting
> workbench. Feeds the **security review gate**. **Status: DRAFT for review.**

## Trust boundaries

```
[Broker docs / external] ──(1)──▶ [Workbench UI] ──(2)──▶ [Underwriting API] ──(3)──▶ [PostgreSQL]
                                                     │
                                    (4) mask+extract │──▶ [Presidio] ──▶ [LiteLLM → vLLM]  (egress)
                                                     │
                                    (5) bind         │──▶ [ktayl-policy-service]  (internal)
                                                     └──▶ [NATS bound-risk event]  (internal)
```

**Boundaries:** (1) untrusted external documents; (2) authenticated user session; (3) data-at-rest;
(4) **PII → AI egress** (the highest-attention boundary); (5) cross-service bind + event publish.

## Assets

Broker/insured **PII & beneficial-owner data**; the **UW decision trail** (integrity-critical, regulated);
**rate tables & guidelines** (integrity-critical — mispricing/appetite bypass); the **bind capability**
(authority — an unauthorised bind creates a real liability); LLM provider credentials.

## STRIDE-lite

| # | Threat (STRIDE) | Boundary | Risk | Control (design-time) |
|---|---|---|---|---|
| T1 | **Spoofing** — unauthenticated access | (2) | High | Authentik OIDC + MFA; no anonymous routes; short sessions |
| T2 | **Tampering** — decision trail or rate table altered | (3) | **Critical** | Append-only/immutable audit + version tables (ADR-004); DB perms; no destructive-update code path |
| T3 | **Repudiation** — "I didn't make that decision" | (2)(3) | High | who/when/why on every decision (AUD-1); signed commits for rule/rate changes |
| T4 | **Information disclosure** — PII leaks to the LLM provider | **(4)** | **Critical** | **Presidio masking before any LLM call (SEC-4)**; egress allow-list to LiteLLM only; provider in ICT register; Langfuse audit |
| T5 | **Information disclosure** — cross-tenant/role data | (2)(3) | High | per-role RBAC (UW/senior/manager/compliance); row-level scoping by team |
| T6 | **DoS** — extraction jobs saturate the service | (4) | Medium | async queue (KEDA), rate limits; UI never blocks on the AI path (AVL-2) |
| T7 | **Elevation of privilege** — bind above authority | (5) | **Critical** | **authority matrix enforced server-side (SEC-6)**; referral trigger; bind is authZ-checked, not client-trusted |
| T8 | **Prompt injection** via malicious submission doc | (1)(4) | High | treat extraction output as **untrusted** → human verification (AI-1); structured-schema extraction; no tool-use/actions from extraction in v1 |
| T9 | **Tampering** — forged bind to PAS | (5) | High | signed/authenticated bind contract; idempotency key; PAS validates caller (mTLS/OIDC) |
| T10 | **Supply chain** — compromised image/dependency | build | Medium | Cosign + SBOM + Trivy CRITICAL gate (SEC-5) |
| T11 | **Compliance** — sanctioned counterparty bound | (5) | High | **sanctions/PEP screening gate before bind**; captured in the trail (AML) |

## Residual risks / accepted (v1)

- **No autonomous AI action** — deliberately out of scope; the high-tier AI-Act controls are only required
  when the parked copilot is built. Accepted, documented, revisit-gated.
- **Local entity model (no MDM)** — a de-duplication/quality risk on shared entities, accepted until a 2nd
  consumer forces MDM (ADR-002).

## Verification

Threats map to gate checks: T1/T5 (RBAC test), T2/T3 (immutability + audit query), **T4/T8 (PII-mask +
human-verify flow test — the security-gate blocker)**, T7/T11 (authority + screening enforced before bind),
T10 (supply-chain CI). Evidence lands in the **Compliance #15** control library.
