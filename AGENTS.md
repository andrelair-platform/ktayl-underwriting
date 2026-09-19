# AGENTS.md — ktayl-underwriting

Tiny verified context for agents. **Not** a repo overview (the code + the [docs](./docs/) are the context).
Policy, command catches, and non-default conventions only.

## Policy
- This is the **ktayl-solution insurance IS** (business context), **not** the RNCP certification (that is
  **Retrieva**, a separate product). Never label this repo's work as cert evidence.
- **Planning-first / review gate:** the BMAD artefacts in `docs/` ([brief](./docs/brief.md),
  [prd](./docs/prd.md), [architecture/](./docs/architecture/)) are reviewed **before** implementation.
  Do not start feature code until the brief/PRD/architecture are approved.
- **Thin slice first** (playbook §10): build ONE LOB end-to-end that actually **binds** into
  `ktayl-policy-service`; defer UW-03 (committee) and UW-05 (cat/aggregate). Do not build 5 half-epics.
- **AI is assistive + human-verified only** (ADR-003). No autonomous action; the AI Ops Copilot (#19) is
  **parked**. **Presidio-mask PII before any LLM call** (threat T4 — the security-gate blocker).
- **No standalone MDM** — local entity model until a 2nd consumer (ADR-002). Do not block on MDM.

## Conventions (non-default)
- Container build file is named **`Dockerfile`** (never `Containerfile`).
- Delivery is **GitOps (ArgoCD) + Kargo** dev→prod; prod is CODEOWNERS-gated. Images are env-agnostic
  (runtime config), Cosign-signed + SBOM, ghcr for prod / Harbor for dev.
- Secrets via **ESO→Vault**; SSO via **Authentik OIDC**; TLS via **cert-manager**; default-deny
  NetworkPolicies with an explicit egress allow-list.
- Rate tables + guidelines are **versioned/immutable/auditable**; the decision trail is **append-only**
  (ADR-004). No in-place destructive updates on those tables.
- Stories live in `bmad/stories/underwriting/` and sync to issues on **board #12** via the org-shared
  reusable workflow (frontmatter `repo:` / `project: 12`).

## Pitfalls
- The **bind contract** to `ktayl-policy-service` must be authenticated + idempotent (ADR-006) — a forged/
  duplicate bind is a real liability (threats T7/T9).
- Treat **extraction output as untrusted** (prompt-injection T8) — structured-schema + human verification;
  never let extraction take an action in v1.
