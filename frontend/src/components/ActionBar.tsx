"use client";

import { useState, useTransition } from "react";

import { assessAction, bindAction, quoteAction, type ActionResult } from "@/app/submissions/actions";

interface Props {
  submissionId: string;
  canAssess: boolean;
  canQuote: boolean;
  canBind: boolean;
  bound: boolean;
}

type Kind = "assess" | "quote" | "bind";

export function ActionBar({ submissionId, canAssess, canQuote, canBind, bound }: Props) {
  const [pending, startTransition] = useTransition();
  const [running, setRunning] = useState<Kind | null>(null);
  const [error, setError] = useState<string | null>(null);

  function run(kind: Kind, fn: (id: string) => Promise<ActionResult>) {
    setError(null);
    setRunning(kind);
    startTransition(async () => {
      const result = await fn(submissionId);
      if (!result.ok) setError(result.error ?? "action failed");
      setRunning(null);
    });
  }

  if (bound) {
    return (
      <p className="text-sm text-slate-500">
        This submission is <strong>bound</strong> — it is frozen (re-assess and re-quote are locked).
      </p>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!canAssess || pending}
          onClick={() => run("assess", assessAction)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running === "assess" ? "Assessing…" : "Assess appetite"}
        </button>
        <button
          type="button"
          disabled={!canQuote || pending}
          onClick={() => run("quote", quoteAction)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running === "quote" ? "Rating…" : "Rate & quote"}
        </button>
        <button
          type="button"
          disabled={!canBind || pending}
          onClick={() => run("bind", bindAction)}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running === "bind" ? "Binding…" : "Bind to policy"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
    </div>
  );
}
