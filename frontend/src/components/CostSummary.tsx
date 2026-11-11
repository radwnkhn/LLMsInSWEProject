"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

import { ApiError, api } from "@/lib/api";
import { formatCost, formatTokens } from "@/lib/format";
import type { CostSummary as Summary } from "@/lib/types";

/** A share as a whole percent; a real share under 1% reads "<1%" rather than looking like nothing. */
function percent(share: number | null): string {
  if (share === null) return "–";
  if (share > 0 && share < 0.01) return "<1%";
  return `${Math.round(share * 100)}%`;
}

function unknownNote(count: number): string {
  return count === 1 ? "1 attempt has an unknown cost and isn't included."
    : `${count} attempts have an unknown cost and aren't included.`;
}

/** US-26: LLM cost of the analyses created in a date range (the API defaults to the last 30 days). */
export function CostSummary({ token }: { token: string | null }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fromId = useId();
  const toId = useId();

  async function load(from: string | null, to: string | null) {
    setError(null);
    try {
      const s = await api.adminCosts(from, to, token);
      setSummary(s);
      setStart(s.start);
      setEnd(s.end);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load AI costs. Please try again.");
    }
  }

  useEffect(() => { void load(null, null); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function show(e: FormEvent) {
    e.preventDefault();
    void load(start || null, end || null);
  }

  return (
    <section aria-label="AI cost" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="text-lg font-semibold">AI cost</h2>
      <form onSubmit={show} className="flex flex-wrap items-end gap-3 text-sm">
        <div>
          <label htmlFor={fromId} className="block">From</label>
          <input id={fromId} type="date" value={start} onChange={(e) => setStart(e.target.value)}
            className="rounded-lg border border-zinc-300 px-2 py-1" />
        </div>
        <div>
          <label htmlFor={toId} className="block">To</label>
          <input id={toId} type="date" value={end} onChange={(e) => setEnd(e.target.value)}
            className="rounded-lg border border-zinc-300 px-2 py-1" />
        </div>
        <button type="submit" className="rounded-lg border border-zinc-300 px-3 py-1 font-medium">Show</button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {summary && summary.analysis_count === 0 && (
        <p className="text-sm text-zinc-600">No analyses with AI attempts in this range.</p>
      )}
      {summary && summary.analysis_count > 0 && (
        <>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><dt className="text-zinc-500">Total cost</dt><dd className="text-lg font-semibold">{formatCost(summary.total_cost)}</dd></div>
            <div><dt className="text-zinc-500">Analyses</dt><dd className="text-lg font-semibold">{summary.analysis_count}</dd></div>
            <div><dt className="text-zinc-500">Average per analysis</dt><dd className="text-lg font-semibold">{formatCost(summary.average_cost)}</dd></div>
            <div><dt className="text-zinc-500">Spent on correction retries</dt><dd className="text-lg font-semibold">
              {percent(summary.retry_share)}</dd></div>
          </dl>
          <p className="text-xs text-zinc-500">
            {formatTokens(summary.input_tokens)} in / {formatTokens(summary.output_tokens)} out tokens over{" "}
            {summary.attempt_count} attempts ({summary.retry_attempt_count} retries). Estimates at the prices in the
            price table.
          </p>
          {summary.unknown_cost_attempts > 0 && (
            <p className="text-sm text-amber-800">{unknownNote(summary.unknown_cost_attempts)}</p>
          )}
        </>
      )}
    </section>
  );
}
