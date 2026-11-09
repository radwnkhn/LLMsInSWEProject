import type { ProcessingStage } from "@/lib/types";

const STEPS = [
  { id: "uploading", label: "Uploading" },
  { id: "measuring", label: "Measuring" },
  { id: "writing_feedback", label: "Writing feedback" },
  { id: "checking", label: "Checking" },
] as const;

export function AnalysisProgress({ stage }: { stage: ProcessingStage | "uploading" | null }) {
  const current = STEPS.findIndex((step) => step.id === stage);
  return (
    <section className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <p role="status" aria-live="polite" className="text-sm text-zinc-700">
        {stage === "uploading" ? "Uploading your video…" : `Analyzing your set… ${current < 0 ? "Waiting to measure" : STEPS[current].label}…`}
      </p>
      <ol aria-label="Analysis progress" className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {STEPS.map((step, index) => (
          <li key={step.id} className={`rounded-lg border px-2 py-2 ${index === current
            ? "border-zinc-900 bg-zinc-900 font-semibold text-white"
            : index < current || (current < 0 && index === 0)
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-zinc-200 text-zinc-500"}`}>
            <span aria-current={index === current ? "step" : undefined}>{step.label}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
