// Liveness/readiness probe target for Kubernetes — a same-origin endpoint that does NOT touch the
// backend (so the frontend's own health is independent of the API's).
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
