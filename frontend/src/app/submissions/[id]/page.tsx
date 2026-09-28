import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionBar } from "@/components/ActionBar";
import { OutcomeBadge } from "@/components/OutcomeBadge";
import { ApiError, api, orNull } from "@/lib/api";
import { formatEurCents } from "@/lib/money";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{children}</dd>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

export default async function SubmissionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let submission;
  try {
    submission = await api.getSubmission(id);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const [quote, binding, audit] = await Promise.all([
    orNull(api.getQuote(id)),
    orNull(api.getBinding(id)),
    api.getAudit(id).catch(() => []),
  ]);

  const decision = submission.latest_decision;
  const bound = binding !== null;
  const canAssess = !bound;
  const canQuote = !bound && decision !== null && decision.outcome !== "decline";
  const canBind = !bound && decision?.outcome === "accept" && quote !== null;

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">
          ← Inbox
        </Link>
        <span className="text-slate-300">/</span>
        <h1 className="font-mono text-sm text-slate-700">{submission.id}</h1>
        {bound ? (
          <OutcomeBadge outcome="bound" />
        ) : (
          <OutcomeBadge outcome={decision?.outcome ?? "unassessed"} />
        )}
      </div>

      <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5">
        <ActionBar
          submissionId={submission.id}
          canAssess={canAssess}
          canQuote={canQuote}
          canBind={canBind}
          bound={bound}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Risk">
          <dl className="grid grid-cols-2 gap-4">
            <Field label="Line of business">{submission.line_of_business.replaceAll("_", " ")}</Field>
            <Field label="Occupancy">{submission.occupancy.replaceAll("_", " ")}</Field>
            <Field label="Total insured value">{formatEurCents(submission.tiv_eur)}</Field>
            <Field label="Risk location">
              {submission.country} · {submission.postcode}
            </Field>
            <Field label="Requested cover">{submission.requested_cover}</Field>
            <Field label="Broker ref">{submission.broker_ref ?? "—"}</Field>
          </dl>
        </Card>

        <Card title="Appetite decision">
          {decision ? (
            <dl className="grid grid-cols-2 gap-4">
              <Field label="Outcome">
                <OutcomeBadge outcome={decision.outcome} />
              </Field>
              <Field label="Ruleset version">v{decision.appetite_version}</Field>
              <div className="col-span-2">
                <Field label="Reason codes">
                  <ul className="mt-1 flex flex-wrap gap-1">
                    {decision.reason_codes.map((code) => (
                      <li key={code} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-600">
                        {code}
                      </li>
                    ))}
                  </ul>
                </Field>
              </div>
              <Field label="Decided by">{decision.decided_by}</Field>
              <Field label="Decided at">{new Date(decision.decided_at).toLocaleString()}</Field>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Not assessed yet — run “Assess appetite”.</p>
          )}
        </Card>

        <Card title="Rating & quote">
          {quote ? (
            <div>
              <div className="mb-4 flex items-baseline justify-between">
                <span className="text-2xl font-semibold text-slate-900">{formatEurCents(quote.premium_minor)}</span>
                <span className="text-xs text-slate-400">rate table v{quote.rate_table_version}</span>
              </div>
              <table className="min-w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th className="py-1">Step</th>
                    <th className="py-1">Kind</th>
                    <th className="py-1 text-right">Value</th>
                    <th className="py-1 text-right">Running</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {quote.breakdown.map((li, idx) => (
                    <tr key={idx}>
                      <td className="py-1 text-slate-700">{li.label}</td>
                      <td className="py-1 text-slate-500">{li.kind}</td>
                      <td className="py-1 text-right tabular-nums text-slate-600">{li.value}</td>
                      <td className="py-1 text-right tabular-nums text-slate-800">
                        {formatEurCents(li.running_subtotal_minor)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No quote yet — assess (accept/refer) then “Rate &amp; quote”.</p>
          )}
        </Card>

        <Card title="Policy binding">
          {binding ? (
            <dl className="grid grid-cols-2 gap-4">
              <Field label="Policy number">
                <span className="font-mono">{binding.policy_number}</span>
              </Field>
              <Field label="Status">{binding.status}</Field>
              <Field label="PAS policy id">{binding.pas_policy_id ?? "—"}</Field>
              <Field label="bound-risk event">{binding.event_published ? "published" : "pending"}</Field>
              <Field label="Bound by">{binding.bound_by}</Field>
              <Field label="Bound at">{new Date(binding.created_at).toLocaleString()}</Field>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Not bound. Bind an accepted, quoted submission to create the policy.</p>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <Card title="Audit trail">
        {audit.length === 0 ? (
          <p className="text-sm text-slate-500">No audit entries.</p>
        ) : (
          <ol className="space-y-2">
            {audit.map((entry) => (
              <li key={entry.id} className="flex items-center gap-3 text-sm">
                <span className="w-40 shrink-0 text-slate-400">{new Date(entry.created_at).toLocaleString()}</span>
                <span className="font-mono text-slate-700">{entry.action}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-500">{entry.actor}</span>
              </li>
            ))}
          </ol>
        )}
        </Card>
      </div>
    </div>
  );
}
