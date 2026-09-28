import type { Outcome } from "@/lib/types";

const STYLES: Record<Outcome | "unassessed" | "bound", string> = {
  accept: "bg-green-100 text-green-800 ring-green-600/20",
  refer: "bg-amber-100 text-amber-800 ring-amber-600/20",
  decline: "bg-red-100 text-red-800 ring-red-600/20",
  unassessed: "bg-slate-100 text-slate-600 ring-slate-500/20",
  bound: "bg-indigo-100 text-indigo-800 ring-indigo-600/20",
};

const LABELS: Record<Outcome | "unassessed" | "bound", string> = {
  accept: "Accept",
  refer: "Refer",
  decline: "Decline",
  unassessed: "Unassessed",
  bound: "Bound",
};

export function OutcomeBadge({ outcome }: { outcome: Outcome | "unassessed" | "bound" }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[outcome]}`}
    >
      {LABELS[outcome]}
    </span>
  );
}
