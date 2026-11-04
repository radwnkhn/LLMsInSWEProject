"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";

import { AnnotatedFrame } from "@/components/AnnotatedFrame";
import { FeedbackForm } from "@/components/FeedbackForm";
import { NotMeasured } from "@/components/NotMeasured";
import { PreviousCuePrompt } from "@/components/PreviousCuePrompt";
import { RepBreakdown } from "@/components/RepBreakdown";
import type { AnalysisResult, FaultView, FeedbackAnswer, TriedCue } from "@/lib/types";

type Props = {
  result: AnalysisResult;
  onFeedback: (answer: FeedbackAnswer) => Promise<void>;
  onPreviousCueAnswer?: (analysisId: string, tried: TriedCue) => Promise<void>;
};

function SafetyLabel() {
  return <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Safety issue</span>;
}

function TopFix({ fix, cue, explanation }: { fix: FaultView; cue: string | null; explanation: string | null }) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="space-y-2 rounded-xl border-2 border-zinc-900 p-4">
      <div className="flex items-center gap-2">
        <h2 id={titleId} className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Top fix</h2>
        {fix.safety && <SafetyLabel />}
      </div>
      <p className="text-xl font-bold">{fix.title}</p>
      {cue && (
        <p className="rounded-lg bg-zinc-900 px-3 py-2 font-medium text-white" aria-label="Cue for your next set">{cue}</p>
      )}
      {explanation && <p className="text-sm text-zinc-700">{explanation}</p>}
    </section>
  );
}

function SeeMore({ faults }: { faults: FaultView[] }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  return (
    <div>
      <button type="button" aria-expanded={open} aria-controls={listId} onClick={() => setOpen(!open)}
        className="text-sm font-medium underline">See more</button>
      {open && (
        <ul id={listId} className="mt-2 space-y-1 text-sm">
          {faults.map((f) => (
            <li key={f.fault_id} className="flex items-center gap-2">
              <span>{f.title}</span>
              <span className="text-zinc-500">reps {f.reps.join(", ")}</span>
              {f.safety && <SafetyLabel />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ResultsView({ result, onFeedback, onPreviousCueAnswer }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  if (result.status === "queued" || result.status === "processing") {
    return <p role="status" className="animate-pulse text-zinc-600">Analyzing your set… this usually takes under a minute.</p>;
  }
  if (result.status === "failed") {
    return (
      <div role="alert" className="space-y-2 rounded-xl bg-red-50 p-4 text-red-800">
        <p>Something went wrong analyzing this video. Please try uploading it again.</p>
        <Link href="/upload" className="font-semibold underline">Upload again</Link>
      </div>
    );
  }

  function seek(seconds: number, play: boolean) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = seconds;
    video.scrollIntoView?.({ behavior: "smooth", block: "center" });
    if (play) video.play()?.catch(() => {});
  }

  const unanalyzable = result.final_status === "unanalyzable";
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{result.lift_label}</h1>
        {!unanalyzable && result.rep_count !== null && <p className="text-sm text-zinc-600">{result.rep_count} reps</p>}
      </header>

      {result.professional_message && (
        <aside role="note" aria-label="See a professional" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
          {result.professional_message}
        </aside>
      )}

      {unanalyzable && (
        <section className="space-y-3 rounded-xl bg-zinc-100 p-4">
          <h2 className="text-lg font-semibold">{result.unanalyzable_reason}</h2>
          <p className="text-sm text-zinc-700">Check the filming tips and record the set again.</p>
          <Link href={`/upload?lift=${result.lift}&guide=1`}
            className="inline-block rounded-lg bg-zinc-900 px-4 py-2 font-semibold text-white">Refilm</Link>
        </section>
      )}

      {result.fallback_note && <p className="rounded-xl bg-zinc-100 p-4 text-sm">{result.fallback_note}</p>}

      {result.previous_cue_prompt && (
        <PreviousCuePrompt prompt={result.previous_cue_prompt} onAnswer={onPreviousCueAnswer ?? (async () => {})} />
      )}

      {result.top_fix && <TopFix fix={result.top_fix} cue={result.cue} explanation={result.explanation} />}
      {result.no_major_issues && (
        <div className="rounded-xl bg-emerald-50 p-4 text-emerald-800">
          <p className="font-semibold">No major issues found</p>
          {result.not_measured.length > 0 && (
            <p className="mt-1 text-sm">
              {result.not_measured.length === 1
                ? "1 check couldn't be run from this video, so it isn't covered."
                : `${result.not_measured.length} checks couldn't be run from this video, so they aren't covered.`}
              {" "}See &quot;Not measured&quot; below.
            </p>
          )}
        </div>
      )}
      {result.other_faults.length > 0 && <SeeMore faults={result.other_faults} />}

      {result.video_url && !unanalyzable && (
        <video ref={videoRef} src={result.video_url} controls playsInline preload="metadata" className="w-full rounded-xl bg-black" />
      )}
      {result.annotated_frame && <AnnotatedFrame frame={result.annotated_frame} onPlayFrom={(t) => seek(t, true)} />}
      {result.rep_breakdown && <RepBreakdown breakdown={result.rep_breakdown} onSeek={(t) => seek(t, false)} />}
      <NotMeasured items={result.not_measured} />

      <FeedbackForm initial={result.feedback} onSubmit={onFeedback} showCueQuestion={Boolean(result.cue)} />
    </div>
  );
}
