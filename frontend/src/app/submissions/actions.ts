"use server";

// Server actions for the workbench writes. They run on the Next.js server (never the browser), call
// the backend via the server-only api client, then revalidate the affected pages so the UI reflects
// the new state. Each returns a small {ok|error} result the client components render inline.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import type { LineOfBusiness, Occupancy, SubmissionCreate } from "@/lib/types";

export interface ActionResult {
  ok: boolean;
  error?: string;
}

function toResult(e: unknown): ActionResult {
  if (e instanceof ApiError) return { ok: false, error: `${e.status}: ${e.detail}` };
  return { ok: false, error: e instanceof Error ? e.message : "unexpected error" };
}

export async function assessAction(id: string): Promise<ActionResult> {
  try {
    await api.assess(id);
  } catch (e) {
    return toResult(e);
  }
  revalidatePath(`/submissions/${id}`);
  revalidatePath("/");
  return { ok: true };
}

export async function quoteAction(id: string): Promise<ActionResult> {
  try {
    await api.quote(id);
  } catch (e) {
    return toResult(e);
  }
  revalidatePath(`/submissions/${id}`);
  return { ok: true };
}

export async function bindAction(id: string): Promise<ActionResult> {
  try {
    await api.bind(id);
  } catch (e) {
    return toResult(e);
  }
  revalidatePath(`/submissions/${id}`);
  revalidatePath("/");
  return { ok: true };
}

// Intake: create a submission from the form, then redirect to its detail page. Returns an error
// result on validation/API failure (redirect throws internally, so it must sit outside the try).
export async function createSubmissionAction(
  _prev: ActionResult | null,
  formData: FormData,
): Promise<ActionResult> {
  const tivEur = Number(formData.get("tiv_eur"));
  const payload: SubmissionCreate = {
    counterparty: {
      name: String(formData.get("counterparty_name") ?? "").trim(),
      country: String(formData.get("counterparty_country") ?? "").trim().toUpperCase(),
    },
    line_of_business: String(formData.get("line_of_business")) as LineOfBusiness,
    tiv_eur: Number.isFinite(tivEur) ? Math.round(tivEur * 100) : 0, // euros in the form → eurocents
    occupancy: String(formData.get("occupancy")) as Occupancy,
    country: String(formData.get("country") ?? "").trim().toUpperCase(),
    postcode: String(formData.get("postcode") ?? "").trim(),
    requested_cover: String(formData.get("requested_cover") ?? "").trim(),
    broker_ref: (String(formData.get("broker_ref") ?? "").trim() || null) as string | null,
  };

  let createdId: string;
  try {
    const created = await api.createSubmission(payload);
    createdId = created.id;
  } catch (e) {
    return toResult(e);
  }
  revalidatePath("/");
  redirect(`/submissions/${createdId}`);
}
