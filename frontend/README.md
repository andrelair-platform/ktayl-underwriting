# ktayl-underwriting — frontend (underwriter workbench)

Next.js 16 (App Router) + React 19 + Tailwind v4 UI for the `ktayl-underwriting` service. It is the
AI-native **task inbox**: the system auto-decides the rule (accept / decline); underwriters work the
**referrals**.

## Architecture — a BFF, not a browser-side SPA

The browser only talks **same-origin** to this Next.js app. Reads are **server components**; writes are
**server actions**. Both reach the backend API **server-side** via `src/lib/api.ts`, which reads the API
base from `API_URL` **at runtime** (never baked) — so one image serves dev and prod, and the underwriting
API is never exposed to the browser.

```
Browser ──(same origin)──▶ Next.js (server components + server actions) ──(API_URL, server-side)──▶ ktayl-underwriting API
```

| Page | Route | Kind |
|---|---|---|
| Inbox (queue, filter by outcome) | `/` | server component → `GET /v1/submissions` |
| Submission detail (decision, rating breakdown, binding, audit) | `/submissions/[id]` | server component |
| New submission | `/submissions/new` | client form → `createSubmissionAction` |
| Health probe | `/healthz` | route handler (does not touch the API) |

Actions (`src/app/submissions/actions.ts`): `assess`, `quote`, `bind`, `createSubmission`.

## Develop

```bash
npm install
API_URL=http://localhost:8000 npm run dev   # point at a running backend
npm run lint      # L0 — eslint (next flat config)
npm run test      # L1 — vitest (jsdom)
npm run build     # typecheck + compile (output: standalone)
```

## Environment

| Var | Default | Notes |
|---|---|---|
| `API_URL` | `http://localhost:8000` | backend base URL, read **server-side at runtime** |
| `UW_API_TOKEN` | — | optional bearer forwarded to the API (prod auth gate; unused in dev where the API runs auth-OFF) |
| `PORT` / `HOSTNAME` | `3000` / `0.0.0.0` | standalone server bind |

## Build image

`docker build -t ktayl-underwriting-frontend:dev frontend/` — multi-stage, `output: standalone`, non-root.
Runs on port 3000. CI builds backend + frontend from the **same commit** with the same tag in separate
repos (`library/ktayl-underwriting` + `library/ktayl-underwriting-frontend`); Kargo's git-Warehouse pins
both to the commit SHA so a promotion always moves a consistent pair.
