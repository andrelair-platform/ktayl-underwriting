// TypeScript mirrors of the ktayl-underwriting API schemas (app/*/schemas.py). Kept deliberately
// hand-written and small — the workbench only needs the read shapes + a couple of write payloads.

export type Outcome = "accept" | "refer" | "decline";

export type LineOfBusiness =
  | "commercial_property"
  | "marine"
  | "engineering"
  | "financial_lines";

export type Occupancy =
  | "office"
  | "retail"
  | "warehouse"
  | "light_manufacturing"
  | "fireworks_manufacturing";

export interface SubmissionListItem {
  id: string;
  counterparty_id: string;
  line_of_business: LineOfBusiness;
  tiv_eur: number; // eurocents (minor units)
  occupancy: Occupancy;
  country: string;
  postcode: string;
  requested_cover: string;
  broker_ref: string | null;
  created_at: string;
  latest_outcome: Outcome | null;
  bound: boolean;
}

export interface Decision {
  id: string;
  submission_id: string;
  outcome: Outcome;
  reason_codes: string[];
  appetite_version: number;
  decided_by: string;
  decided_at: string;
}

export interface SubmissionDetail extends Omit<SubmissionListItem, "latest_outcome" | "bound"> {
  latest_decision: Decision | null;
}

export interface LineItem {
  label: string;
  kind: "base" | "factor" | "loading" | "discount" | string;
  value: string;
  running_subtotal_minor: number;
}

export interface Quote {
  id: string;
  submission_id: string;
  premium_minor: number; // eurocents
  currency: string;
  rate_table_version: number;
  breakdown: LineItem[];
  created_by: string;
  created_at: string;
}

export interface Binding {
  id: string;
  submission_id: string;
  quote_id: string;
  policy_number: string;
  pas_policy_id: string | null;
  status: string;
  event_published: boolean;
  bound_by: string;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  submission_id: string;
  action: string;
  actor: string;
  detail: Record<string, unknown> | null;
  created_at: string;
}

// The intake form payload (POST /v1/submissions).
export interface SubmissionCreate {
  counterparty: { name: string; country: string };
  line_of_business: LineOfBusiness;
  tiv_eur: number;
  occupancy: Occupancy;
  country: string;
  postcode: string;
  requested_cover: string;
  broker_ref?: string | null;
}
