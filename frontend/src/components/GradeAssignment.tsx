"use client";

import { useId, useState, type FormEvent } from "react";

import { ApiError, api } from "@/lib/api";
import type { OurFeedback, TrainerAssignment, Verdict } from "@/lib/types";

const VERDICTS: { value: Verdict; label: string }[] = [
  { value: "correct", label: "Correct" },
  { value: "partly_correct", label: "Partly correct" },
  { value: "wrong", label: "Wrong" },
];
const NO_FAULT = "none"; // the radio value for "No major issue" (sent as fault_id null)
const button = "rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white";

function message(err: unknown): string {
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

function OwnAnswer({ assignment, token, onSaved }: {
  assignment: TrainerAssignment; token: string | null; onSaved: (a: TrainerAssignment) => void;
}) {
  const [choice, setChoice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const name = useId();

  async function save(e: FormEvent) {
    e.preventDefault();
    if (choice === null) return setError("Choose a fault, or No major issue");
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.answerAssignment(assignment.assignment_id, choice === NO_FAULT ? null : choice, token));
    } catch (err) {
      setError(message(err));
      setSaving(false);
    }
  }

  return (
    <section aria-label="Your top fault" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="text-lg font-semibold">1. Your top fault</h2>
      <p className="text-sm text-zinc-600">
        What is the one thing this lifter should fix first? Our feedback is shown after you save, and your answer
        can&apos;t be changed then.
      </p>
      <form onSubmit={(e) => void save(e)} className="space-y-2" noValidate>
        <fieldset className="space-y-1">
          <legend className="sr-only">Top fault</legend>
          {assignment.fault_options.map((o) => {
            const value = o.fault_id ?? NO_FAULT;
            return (
              <label key={value} className="flex items-center gap-2 text-sm">
                <input type="radio" name={name} value={value} checked={choice === value} onChange={() => setChoice(value)} />
                {o.name}
              </label>
            );
          })}
        </fieldset>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={saving} className={button}>Save my answer</button>
      </form>
    </section>
  );
}

function Feedback({ ours }: { ours: OurFeedback }) {
  return (
    <section aria-label="Our feedback" className="space-y-2 rounded-xl bg-zinc-100 p-4">
      <h2 className="text-lg font-semibold">2. Our feedback</h2>
      {ours.top_fix ? (
        <>
          <p className="font-medium">Top fix: {ours.top_fix.title} (reps {ours.top_fix.reps.join(", ")})</p>
          {ours.cue && <p className="text-sm">Cue: {ours.cue}</p>}
        </>
      ) : <p className="font-medium">No major issues found</p>}
      {ours.explanation && <p className="text-sm text-zinc-700">{ours.explanation}</p>}
      {ours.other_faults.length > 0 && (
        <div className="text-sm">
          <p className="text-zinc-600">Also reported:</p>
          <ul className="list-inside list-disc">
            {ours.other_faults.map((f) => <li key={f.fault_id}>{f.title} (reps {f.reps.join(", ")})</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

function Grade({ assignment, token, onSaved }: {
  assignment: TrainerAssignment; token: string | null; onSaved: (a: TrainerAssignment) => void;
}) {
  const [verdict, setVerdict] = useState<Verdict | null>(assignment.verdict);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(assignment.verdict_label);
  const [saving, setSaving] = useState(false);
  const name = useId();

  async function save(e: FormEvent) {
    e.preventDefault();
    if (verdict === null) return setError("Choose a grade");
    setSaving(true);
    setError(null);
    try {
      const updated = await api.gradeAssignment(assignment.assignment_id, verdict, token);
      setSaved(updated.verdict_label);
      onSaved(updated);
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-label="Your grade" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="text-lg font-semibold">3. Your grade</h2>
      <p className="text-sm text-zinc-600">Is our feedback right for this set?</p>
      <form onSubmit={(e) => void save(e)} className="space-y-2" noValidate>
        <fieldset className="space-y-1">
          <legend className="sr-only">Grade</legend>
          {VERDICTS.map((v) => (
            <label key={v.value} className="flex items-center gap-2 text-sm">
              <input type="radio" name={name} value={v.value} checked={verdict === v.value} onChange={() => setVerdict(v.value)} />
              {v.label}
            </label>
          ))}
        </fieldset>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {saved && <p role="status" className="text-sm text-green-800">Saved: {saved}</p>}
        <button type="submit" disabled={saving} className={button}>Save grade</button>
      </form>
    </section>
  );
}

/** US-22: grade one set blind. Our feedback only appears once the trainer's own top fault is saved. */
export function GradeAssignment({ initial, token }: { initial: TrainerAssignment; token: string | null }) {
  const [assignment, setAssignment] = useState(initial);
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Grade this set: {assignment.lift_label}</h1>
        <p className="text-sm text-zinc-600">{assignment.status_label}</p>
      </header>
      <video src={assignment.video_url} controls playsInline preload="metadata" className="w-full rounded-xl bg-black" />
      {assignment.trainer_answer === null ? (
        <OwnAnswer assignment={assignment} token={token} onSaved={setAssignment} />
      ) : (
        <>
          <p className="font-medium">Your top fault: {assignment.trainer_answer.name}</p>
          {assignment.our_feedback && <Feedback ours={assignment.our_feedback} />}
          <Grade assignment={assignment} token={token} onSaved={setAssignment} />
        </>
      )}
    </div>
  );
}
