"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminForbidden } from "@/components/AdminForbidden";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AdminDetail } from "@/lib/types";

export default function AdminAnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<AdminDetail | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  useEffect(() => {
    api.adminAnalysis(id, getToken()).then(setDetail).catch((err) => setStatus(err instanceof ApiError ? err.status : 0));
  }, [id]);
  if (status === 403) return <AdminForbidden />;
  if (status) return <p role="alert">Couldn&apos;t load this analysis.</p>;
  if (!detail) return <p role="status">Loading…</p>;
  const metricNames = Array.from(new Set(detail.measurements.flatMap((m) => Object.keys(m.metrics))));
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{detail.analysis.lift_label}: {detail.analysis.final_status_label}</h1>
        <p className="text-sm text-zinc-600">{detail.analysis.user_email} · {detail.analysis.attempt_count} attempts</p>
      </header>
      {detail.video_url && <video src={detail.video_url} controls playsInline className="w-full rounded-xl bg-black" />}
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Per-rep measurements</h2>
        <div className="overflow-x-auto">
          <table className="text-left text-xs">
            <thead><tr><th className="pr-3">Rep</th>{metricNames.map((n) => <th key={n} className="pr-3">{n}</th>)}</tr></thead>
            <tbody>
              {detail.measurements.map((m) => (
                <tr key={m.rep}><td className="pr-3">{m.rep}</td>{metricNames.map((n) => <td key={n} className="pr-3">{m.metrics[n] ?? "–"}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">LLM attempts</h2>
        {detail.attempts.map((a) => (
          <article key={a.attempt_number} className="space-y-2 rounded-xl border border-zinc-200 p-3 text-sm">
            <h3 className="font-semibold">
              Attempt {a.attempt_number}: {a.passed ? "passed" : "failed"} · {a.input_tokens + a.output_tokens} tokens
            </h3>
            {a.errors.length > 0 && (
              <ul className="list-disc pl-5 text-red-700">{a.errors.map((e, i) => <li key={i}><code>{e.code}</code> {e.message}</li>)}</ul>
            )}
            <pre className="max-h-64 overflow-auto rounded bg-zinc-100 p-2 text-xs whitespace-pre-wrap">{a.output_text || "(no output)"}</pre>
          </article>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">What the user saw</h2>
        <pre className="max-h-96 overflow-auto rounded bg-zinc-100 p-2 text-xs">{JSON.stringify(detail.result, null, 2)}</pre>
      </section>
    </div>
  );
}
