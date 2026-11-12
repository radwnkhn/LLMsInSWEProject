"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

import { ApiError, api } from "@/lib/api";
import type { HypothesisMetric, MetricKey, MetricStatus, MetricsReport } from "@/lib/types";

const percent = (share: number) => `${Math.round(share * 100)}%`;

// What a "hit" is for each metric, shown after the count, e.g. "Based on 3 graded sets (2 agreed)".
const HITS: Record<MetricKey, string> = {
  trainer_agreement: "agreed", helpful_ratings: "rated 4–5", cue_tried: "tried it", seven_day_return: "came back",
};

const STATUS_STYLE: Record<MetricStatus, string> = {
  on_target: "bg-green-100 text-green-800",
  below_target: "bg-amber-100 text-amber-900",
  failing: "bg-red-100 text-red-800",
  no_data: "bg-zinc-200 text-zinc-700",
};

function MetricCard({ metric, pendingReturns }: { metric: HypothesisMetric; pendingReturns: number }) {
  const titleId = useId();
  const empty = metric.value === null;
  return (
    <section aria-labelledby={titleId} className="space-y-2 rounded-xl border border-zinc-200 p-4">
      <div className="flex items-start justify-between gap-2">
        <h2 id={titleId} className="font-semibold">{metric.label}</h2>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[metric.status]}`}>
          {metric.status_label}
        </span>
      </div>
      <p className="text-3xl font-bold">{empty ? "—" : percent(metric.value as number)}</p>
      <p className="text-sm text-zinc-600">Target: {percent(metric.target)} or more · Fails below {percent(metric.fail_below)}</p>
      <p className="text-sm text-zinc-600">
        {empty ? "No data yet" : `Based on ${metric.basis} (${metric.hits} ${HITS[metric.key]})`}
      </p>
      {metric.key === "seven_day_return" && pendingReturns > 0 && (
        <p className="text-xs text-zinc-500">
          {pendingReturns === 1 ? "1 lifter is" : `${pendingReturns} lifters are`} still within their first 7 days and
          not counted yet.
        </p>
      )}
    </section>
  );
}

/** US-23: are the hypothesis metrics on target? The API defaults to the last 30 days. */
export function MetricsDashboard({ token, onForbidden }: { token: string | null; onForbidden: () => void }) {
  const [report, setReport] = useState<MetricsReport | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fromId = useId();
  const toId = useId();

  async function load(from: string | null, to: string | null) {
    setError(null);
    try {
      const r = await api.adminMetrics(from, to, token);
      setReport(r);
      setStart(r.start);
      setEnd(r.end);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) return onForbidden();
      setError(err instanceof ApiError ? err.detail : "Couldn't load the metrics. Please try again.");
    }
  }

  useEffect(() => { void load(null, null); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function show(e: FormEvent) {
    e.preventDefault();
    void load(start || null, end || null);
  }

  return (
    <div className="space-y-4">
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
      {report && (
        <div className="grid gap-3 sm:grid-cols-2">
          {report.metrics.map((m) => <MetricCard key={m.key} metric={m} pendingReturns={report.pending_returns} />)}
        </div>
      )}
      <p className="text-xs text-zinc-500">
        Grades, ratings and cue answers count for sets analyzed in the range. 7-day return counts lifters whose
        first upload is in the range and at least 7 days old.
      </p>
    </div>
  );
}
