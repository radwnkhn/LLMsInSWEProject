"use client";

import { useState, type FormEvent } from "react";

import type { FeedbackAnswer, TriedCue } from "@/lib/types";

const TRIED: { value: TriedCue; label: string }[] = [
  { value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "not_yet", label: "Not yet" },
];

type Props = {
  initial: FeedbackAnswer | null;
  onSubmit: (answer: FeedbackAnswer) => Promise<void>;
  showCueQuestion?: boolean;
};

export function FeedbackForm({ initial, onSubmit, showCueQuestion = true }: Props) {
  const [rating, setRating] = useState<number | null>(initial?.rating ?? null);
  const [tried, setTried] = useState<TriedCue | null>(initial?.tried_cue ?? null);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await onSubmit({ rating, tried_cue: showCueQuestion ? tried : null });
      setSent(true);
    } catch {
      setError("Couldn't save your feedback. Please try again.");
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <fieldset role="radiogroup" aria-label="How helpful was this feedback?">
        <legend className="text-sm font-medium">How helpful was this feedback?</legend>
        <div className="mt-2 flex gap-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className="flex items-center gap-1 text-sm">
              <input type="radio" name="rating" value={String(n)} checked={rating === n} onChange={() => setRating(n)} />
              {n}
            </label>
          ))}
        </div>
      </fieldset>
      {showCueQuestion && (
        <fieldset role="radiogroup" aria-label="Did you try the cue?">
          <legend className="text-sm font-medium">Did you try the cue?</legend>
          <div className="mt-2 flex gap-3">
            {TRIED.map((t) => (
              <label key={t.value} className="flex items-center gap-1 text-sm">
                <input type="radio" name="tried_cue" value={t.value} checked={tried === t.value} onChange={() => setTried(t.value)} />
                {t.label}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <button type="submit" disabled={rating === null && (!showCueQuestion || tried === null)}
        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
        {initial ? "Update feedback" : "Send feedback"}
      </button>
      {sent && <p className="text-sm text-emerald-700">Thanks for the feedback!</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </form>
  );
}
