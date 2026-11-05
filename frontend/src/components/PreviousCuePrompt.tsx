"use client";

import { useState } from "react";

import { liftNoun } from "@/lib/lifts";
import type { PreviousCuePromptData, TriedCue } from "@/lib/types";

type Props = { prompt: PreviousCuePromptData; onAnswer: (analysisId: string, tried: TriedCue) => Promise<void> };

export function PreviousCuePrompt({ prompt, onAnswer }: Props) {
  const [done, setDone] = useState(false);
  if (done) return <p className="rounded-xl bg-zinc-100 p-4 text-sm">Thanks!</p>;
  const answer = async (tried: TriedCue) => {
    await onAnswer(prompt.analysis_id, tried);
    setDone(true);
  };
  return (
    <section aria-label="Previous cue" className="space-y-2 rounded-xl bg-zinc-100 p-4 text-sm">
      <p>{`Last ${liftNoun(prompt.lift)}, your cue was “${prompt.cue}”. Did you try it?`}</p>
      <div className="flex gap-2">
        {([["yes", "Yes"], ["no", "No"], ["not_yet", "Not yet"]] as const).map(([value, label]) => (
          <button key={value} type="button" onClick={() => void answer(value)}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 font-medium">{label}</button>
        ))}
      </div>
    </section>
  );
}
