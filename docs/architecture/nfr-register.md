# NFR Register — Underwriting & Pricing (#12)

> **BMAD/SA artefact.** The PRD's NFR summary made **measurable** — each row has a target and how it's
> verified. Reviewed at the architecture gate. **Status: DRAFT for review.**

## Performance

| ID | NFR | Target | Verify |
|---|---|---|---|
| PERF-1 | Workbench file view latency | p95 < 1.5s | RED metrics (Grafana), k6 |
| PERF-2 | Premium computation | p95 < 800ms | service metric + load test |
| PERF-3 | Appetite/guideline check | p95 < 1.5s (incl. RAG retrieval) | trace (Tempo) |
| PERF-4 | Submission extraction assist | < 30s per submission (async, non-blocking) | Langfuse latency + worker metric |

## Availability & resilience

| ID | NFR | Target | Verify |
|---|---|---|---|
| AVL-1 | Workbench availability (business hours) | 99.5% | uptime SLO / burn-rate alert |
| AVL-2 | **Graceful degradation** — manual entry always works if extraction/LLM is down | no hard dependency on the AI path | chaos drill: kill LiteLLM, confirm manual flow |
| AVL-3 | Bind path resilience | bind retries + idempotency to `ktayl-policy-service` | contract test + fault injection |

## Scale (simulated insurer)

| ID | NFR | Target |
|---|---|---|
| SCL-1 | Open submissions | hundreds concurrent |
| SCL-2 | Concurrent underwriters | tens |
| SCL-3 | Extraction throughput | queue-backed (KEDA), no head-of-line blocking of the UI |

## Durability / DR

| ID | NFR | Target | Verify |
|---|---|---|---|
| DR-1 | System of record | PostgreSQL, Longhorn PVC, Velero daily | restore test on non-prod ns |
| DR-2 | RPO | ≤ 24h | backup schedule |
| DR-3 | RTO | ≤ 4h | documented restore runbook |
| DR-4 | **Decision trail & versioned tables are append-only/immutable** | no destructive update path | schema review + audit query |

## Security (full analysis in the [Threat Model](./threat-model.md))

| ID | NFR | Target |
|---|---|---|
| SEC-1 | AuthN/Z | Authentik OIDC + MFA; per-role RBAC (UW / senior / manager / compliance) |
| SEC-2 | Secrets | ESO → Vault; none in Git or images |
| SEC-3 | Network | default-deny NetworkPolicies; egress allow-list only (DNS, LiteLLM, Qdrant, Postgres, PAS, NATS) |
| SEC-4 | **PII** | **Presidio masking before any LLM call**; minimisation + retention on submissions |
| SEC-5 | Supply chain | Cosign-signed images + SBOM; Trivy CRITICAL gate |
| SEC-6 | AuthZ on bind | authority-matrix enforced server-side (never client trust) |

## Observability

| ID | NFR | Target |
|---|---|---|
| OBS-1 | RED metrics + traces | Prometheus + OTel→Tempo per service |
| OBS-2 | Logs | Loki (structured) |
| OBS-3 | AI observability | **Langfuse** traces every extraction/RAG call (cost, latency, model, tokens) |
| OBS-4 | Product KPIs = observability | quote turnaround, hit ratio, straight-through, referral rate, rate adequacy (playbook §8) exposed live |

## Explainability & auditability (hard requirements — regulated domain)

| ID | NFR | Target | Verify |
|---|---|---|---|
| EXP-1 | Explainable premium | every quote carries base × factor + loadings/discounts with justification | UI + stored breakdown |
| EXP-2 | Cited appetite decision | in-appetite/refer/decline always returns the guideline reference used | stored citation |
| AUD-1 | Decision trail | who/when/why on every accept/refer/decline/conditions, immutable | audit query |
| AUD-2 | Rate/guideline versioning | every pricing/rule change is versioned with author + approval | version history |
| AI-1 | AI human-in-loop | no AI output persisted to the file without human confirmation | flow review + test |

## Cost

| ID | NFR | Target |
|---|---|---|
| COST-1 | No new cloud spend | reuse self-hosted substrate; AI via LiteLLM within department budget caps |
| COST-2 | Inference | prefer local vLLM; cloud fallback within budget |
