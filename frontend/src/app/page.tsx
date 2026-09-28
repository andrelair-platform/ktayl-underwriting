import Link from "next/link";

import { OutcomeBadge } from "@/components/OutcomeBadge";
import { ApiError, api } from "@/lib/api";
import { formatEurCents } from "@/lib/money";
import type { Outcome, SubmissionListItem } from "@/lib/types";

const TABS: { key: string; label: string; outcome?: Outcome }[] = [
  { key: "all", label: "All" },
  { key: "refer", label: "Referrals", outcome: "refer" },
  { key: "accept", label: "Accepted", outcome: "accept" },
  { key: "decline", label: "Declined", outcome: "decline" },
];

function StatusBadge({ item }: { item: SubmissionListItem }) {
  if (item.bound) return <OutcomeBadge outcome="bound" />;
  return <OutcomeBadge outcome={item.latest_outcome ?? "unassessed"} />;
}

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ outcome?: string }>;
}) {
  const { outcome } = await searchParams;
  const active = TABS.find((t) => t.outcome === outcome) ?? TABS[0];

  let items: SubmissionListItem[] = [];
  let error: string | null = null;
  try {
    items = await api.listSubmissions({ outcome: active.outcome, limit: 100 });
  } catch (e) {
    error = e instanceof ApiError ? `${e.status}: ${e.detail}` : "Could not reach the underwriting API";
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Submission inbox</h1>
          <p className="text-sm text-slate-500">
            The system auto-decides the rule; work the <strong>referrals</strong>.
          </p>
        </div>
      </div>

      <nav className="mb-4 flex gap-1 border-b border-slate-200">
        {TABS.map((tab) => {
          const href = tab.outcome ? `/?outcome=${tab.outcome}` : "/";
          const isActive = tab.key === active.key;
          return (
            <Link
              key={tab.key}
              href={href}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                isActive
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : items.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-white px-4 py-12 text-center text-sm text-slate-500">
          No submissions here yet.{" "}
          <Link href="/submissions/new" className="font-medium text-indigo-600 hover:underline">
            Create one
          </Link>
          .
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Line of business</th>
                <th className="px-4 py-3 text-right">TIV</th>
                <th className="px-4 py-3">Risk location</th>
                <th className="px-4 py-3">Cover</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/submissions/${item.id}`} className="block">
                      <StatusBadge item={item} />
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    <Link href={`/submissions/${item.id}`} className="block hover:text-indigo-700">
                      {item.line_of_business.replaceAll("_", " ")}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatEurCents(item.tiv_eur)}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {item.country} · {item.postcode}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 text-slate-500">{item.requested_cover}</td>
                  <td className="px-4 py-3 text-slate-500">{new Date(item.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
