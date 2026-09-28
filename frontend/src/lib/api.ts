// Server-only API client (the BFF layer). Runs in server components + server actions; the browser
// never imports this. Reads the backend base URL from API_URL at RUNTIME (never baked) → one image
// serves dev and prod. `import "server-only"` fails the build if this is ever pulled into a client bundle.
import "server-only";

import type {
  AuditEntry,
  Binding,
  Decision,
  Outcome,
  Quote,
  SubmissionCreate,
  SubmissionDetail,
  SubmissionListItem,
} from "@/lib/types";

const DEFAULT_BASE_URL = "http://localhost:8000";

function baseUrl(): string {
  return (process.env.API_URL || DEFAULT_BASE_URL).replace(/\/$/, "");
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// Prod auth gate (parked with the service): when the API enforces Authentik scopes, mint/forward a
// client-credentials or on-behalf-of token here (server-side) and attach it. In dev the API runs with
// auth OFF (empty AUTHENTIK_JWKS_URL), so no header is needed. Kept as a seam so wiring it is one place.
function authHeaders(): Record<string, string> {
  const token = process.env.UW_API_TOKEN;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store", // the workbench is always live data
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body — keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listSubmissions: (opts?: { outcome?: Outcome; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (opts?.outcome) q.set("outcome", opts.outcome);
    if (opts?.limit != null) q.set("limit", String(opts.limit));
    if (opts?.offset != null) q.set("offset", String(opts.offset));
    const qs = q.toString();
    return request<SubmissionListItem[]>(`/v1/submissions${qs ? `?${qs}` : ""}`);
  },
  getSubmission: (id: string) => request<SubmissionDetail>(`/v1/submissions/${id}`),
  getQuote: (id: string) => request<Quote>(`/v1/submissions/${id}/quote`),
  getBinding: (id: string) => request<Binding>(`/v1/submissions/${id}/bind`),
  getAudit: (id: string) => request<AuditEntry[]>(`/v1/submissions/${id}/audit`),
  createSubmission: (payload: SubmissionCreate) =>
    request<SubmissionListItem>(`/v1/submissions`, { method: "POST", body: JSON.stringify(payload) }),
  assess: (id: string) => request<Decision>(`/v1/submissions/${id}/assess`, { method: "POST" }),
  quote: (id: string) => request<Quote>(`/v1/submissions/${id}/quote`, { method: "POST" }),
  bind: (id: string) => request<Binding>(`/v1/submissions/${id}/bind`, { method: "POST" }),
};

// A read that tolerates a 404 by returning null (a submission may have no quote/binding yet).
export async function orNull<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
