import Link from "next/link";

import { formatDate } from "@/lib/format";
import type { AnalysisComparison, AnalysisResult } from "@/lib/types";

const MESSAGES = {
  still_present: "Still present in the newer upload",
  not_detected: "Not detected in the newer upload",
  not_measured: "Not measurable in the newer upload",
  no_previous_fault: "No top fault was reported in the earlier upload",
  unavailable: "The earlier upload has measurements only, so there is no validated top fault to compare.",
};

function UploadCard({ result, earlier }: { result: AnalysisResult; earlier: boolean }) {
  const label = earlier ? "Earlier" : "Newer";
  return (
    <section aria-label={`${label} upload`} className="min-w-0 space-y-2 rounded-xl border border-zinc-200 p-3">
      <h2 className="font-semibold">{label} upload</h2>
      <p className="text-xs text-zinc-500">{formatDate(result.created_at)} · {result.camera_angle ?? "Unknown"} view</p>
      <p className="text-sm font-medium">{result.rep_count} reps</p>
      {result.video_url && <video aria-label={`${label} video`} src={result.video_url} controls playsInline preload="metadata"
        className="aspect-video w-full min-w-0 rounded-lg bg-black" />}
      <Link href={`/results/${encodeURIComponent(result.analysis_id)}`} className="inline-block text-sm underline">Full result</Link>
    </section>
  );
}

function valueLabel(value: number | null, unit: string) {
  if (value === null) return "Not measured";
  return `${value.toLocaleString("en-US", { maximumFractionDigits: 3 })}${unit === "°" ? "°" : ""}`;
}

export function ComparisonView({ comparison }: { comparison: AnalysisComparison }) {
  const { older, newer, metrics, fault_comparison: fault } = comparison;
  return (
    <div className="space-y-5">
      <header className="space-y-2">
        <Link href="/history" className="text-sm text-zinc-600 underline">Back to history</Link>
        <h1 className="text-2xl font-bold">Compare {older.lift_label} uploads</h1>
      </header>
      <div className="grid grid-cols-2 gap-3">
        <UploadCard result={older} earlier />
        <UploadCard result={newer} earlier={false} />
      </div>
      <section aria-label="Earlier top fix" className="space-y-2 rounded-xl bg-zinc-100 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Earlier top fix</h2>
        {fault.title && <p className="font-semibold">{fault.title}</p>}
        <p>{MESSAGES[fault.status]}</p>
        {fault.newer_reps.length > 0 && <p className="text-sm">Reps {fault.newer_reps.join(", ")}</p>}
        {fault.status === "not_measured" && <p className="text-sm text-zinc-600">The camera angle, visibility or missing measurements prevent a reliable comparison.</p>}
      </section>
      {older.camera_angle !== newer.camera_angle && <p role="note" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
        These uploads use different camera angles. Interpret changes in measurements with that in mind.
      </p>}
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Key measurements</h2>
        <p className="text-sm text-zinc-600">Minimum or maximum of the measured reps in each set. Unavailable checks are marked, never treated as zero.</p>
        <table aria-label="Key measurements" className="w-full table-fixed text-sm">
          <thead><tr className="border-b border-zinc-300">
            <th scope="col" className="w-[44%] px-2 py-2 text-left">Measurement</th>
            <th scope="col" className="px-1 py-2 text-right">Earlier</th>
            <th scope="col" className="px-1 py-2 text-right">Newer</th>
          </tr></thead>
          <tbody>{metrics.map((metric) => <tr key={metric.metric} className="border-b border-zinc-200">
            <th scope="row" className="px-2 py-3 text-left font-medium">
              {metric.label}
              <span className="block text-xs font-normal text-zinc-500">{metric.aggregation} · {metric.unit}</span>
            </th>
            <td className="break-words px-1 py-3 text-right tabular-nums">{valueLabel(metric.older, metric.unit)}</td>
            <td className="break-words px-1 py-3 text-right tabular-nums">{valueLabel(metric.newer, metric.unit)}</td>
          </tr>)}</tbody>
        </table>
      </section>
    </div>
  );
}
