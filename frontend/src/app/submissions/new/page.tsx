"use client";

import Link from "next/link";
import { useActionState } from "react";

import { createSubmissionAction, type ActionResult } from "@/app/submissions/actions";

const LOBS = ["commercial_property", "marine", "engineering", "financial_lines"];
const OCCUPANCIES = ["office", "retail", "warehouse", "light_manufacturing", "fireworks_manufacturing"];

const labelCls = "block text-xs font-medium uppercase tracking-wide text-slate-500";
const inputCls =
  "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

export default function NewSubmissionPage() {
  const [state, formAction, pending] = useActionState<ActionResult | null, FormData>(
    createSubmissionAction,
    null,
  );

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">
          ← Inbox
        </Link>
        <h1 className="text-xl font-semibold text-slate-900">New submission</h1>
      </div>

      <form action={formAction} className="space-y-5 rounded-lg border border-slate-200 bg-white p-6">
        <fieldset className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <legend className="mb-2 text-sm font-semibold text-slate-700">Counterparty</legend>
          </div>
          <div>
            <label className={labelCls} htmlFor="counterparty_name">
              Name
            </label>
            <input id="counterparty_name" name="counterparty_name" required className={inputCls} />
          </div>
          <div>
            <label className={labelCls} htmlFor="counterparty_country">
              Country (ISO-2)
            </label>
            <input
              id="counterparty_country"
              name="counterparty_country"
              required
              maxLength={2}
              minLength={2}
              placeholder="FR"
              className={inputCls}
            />
          </div>
        </fieldset>

        <fieldset className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <legend className="mb-2 text-sm font-semibold text-slate-700">Risk</legend>
          </div>
          <div>
            <label className={labelCls} htmlFor="line_of_business">
              Line of business
            </label>
            <select id="line_of_business" name="line_of_business" className={inputCls} defaultValue="commercial_property">
              {LOBS.map((v) => (
                <option key={v} value={v}>
                  {v.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls} htmlFor="occupancy">
              Occupancy
            </label>
            <select id="occupancy" name="occupancy" className={inputCls} defaultValue="warehouse">
              {OCCUPANCIES.map((v) => (
                <option key={v} value={v}>
                  {v.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls} htmlFor="tiv_eur">
              Total insured value (EUR)
            </label>
            <input
              id="tiv_eur"
              name="tiv_eur"
              type="number"
              min="1"
              step="0.01"
              required
              placeholder="500000"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="broker_ref">
              Broker ref (optional)
            </label>
            <input id="broker_ref" name="broker_ref" className={inputCls} />
          </div>
          <div>
            <label className={labelCls} htmlFor="country">
              Risk country (ISO-2)
            </label>
            <input id="country" name="country" required maxLength={2} minLength={2} placeholder="FR" className={inputCls} />
          </div>
          <div>
            <label className={labelCls} htmlFor="postcode">
              Postcode
            </label>
            <input id="postcode" name="postcode" required className={inputCls} />
          </div>
          <div className="col-span-2">
            <label className={labelCls} htmlFor="requested_cover">
              Requested cover
            </label>
            <input
              id="requested_cover"
              name="requested_cover"
              required
              placeholder="All-risks property damage + business interruption"
              className={inputCls}
            />
          </div>
        </fieldset>

        {state?.error && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{state.error}</p>
        )}

        <div className="flex justify-end gap-3">
          <Link href="/" className="rounded-md px-4 py-2 text-sm text-slate-600 hover:text-slate-900">
            Cancel
          </Link>
          <button
            type="submit"
            disabled={pending}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {pending ? "Creating…" : "Create submission"}
          </button>
        </div>
      </form>
    </div>
  );
}
