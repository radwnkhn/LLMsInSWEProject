"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useState, type FormEvent } from "react";

import { ApiError, api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { LIFTS } from "@/lib/lifts";
import type { AdminGradingAssignment, Trainer } from "@/lib/types";

const MAX_SAMPLE = 50; // the API's limit (backend/app/grading.py)
const input = "w-full rounded-lg border border-zinc-300 px-2 py-1";
const button = "rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white";

function message(err: unknown): string {
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

function AssignSample({ trainers, token, onAssigned }: { trainers: Trainer[]; token: string | null; onAssigned: () => void }) {
  const [trainerId, setTrainerId] = useState(trainers[0]?.id ?? "");
  const [count, setCount] = useState("10");
  const [lift, setLift] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const ids = { trainer: useId(), count: useId(), lift: useId() };

  async function assign(e: FormEvent) {
    e.preventDefault();
    setDone(null);
    const n = Number(count);
    if (count.trim() === "" || !Number.isInteger(n) || n < 1 || n > MAX_SAMPLE) {
      return setError(`Choose a number from 1 to ${MAX_SAMPLE}`);
    }
    setSaving(true);
    setError(null);
    try {
      const result = await api.assignGrading(trainerId, n, lift || null, token);
      setDone(`Assigned ${result.assigned} of ${result.requested} requested analyses.`);
      onAssigned();
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-label="Assign a sample" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="text-lg font-semibold">Assign a sample</h2>
      <p className="text-sm text-zinc-600">
        Picks finished analyses at random. Trainers record their own top fault before they see ours, and never see
        who the lifter is.
      </p>
      <form onSubmit={(e) => void assign(e)} className="grid gap-3 sm:grid-cols-3" noValidate>
        <div className="text-sm">
          <label htmlFor={ids.trainer} className="block">Trainer</label>
          <select id={ids.trainer} className={input} value={trainerId} onChange={(e) => setTrainerId(e.target.value)}>
            {trainers.map((t) => <option key={t.id} value={t.id}>{t.email}</option>)}
          </select>
        </div>
        <div className="text-sm">
          <label htmlFor={ids.count} className="block">Number of analyses</label>
          <input id={ids.count} className={input} type="number" min={1} max={MAX_SAMPLE} inputMode="numeric"
            value={count} onChange={(e) => setCount(e.target.value)} />
        </div>
        <div className="text-sm">
          <label htmlFor={ids.lift} className="block">Lift</label>
          <select id={ids.lift} className={input} value={lift} onChange={(e) => setLift(e.target.value)}>
            <option value="">All lifts</option>
            {LIFTS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </div>
        {error && <p role="alert" className="text-sm text-red-700 sm:col-span-3">{error}</p>}
        {done && <p role="status" className="text-sm text-green-800 sm:col-span-3">{done}</p>}
        <div className="sm:col-span-3">
          <button type="submit" disabled={saving} className={button}>Assign</button>
        </div>
      </form>
    </section>
  );
}

function Assignments({ items }: { items: AdminGradingAssignment[] }) {
  return (
    <section aria-label="Assignments" className="space-y-2">
      <h2 className="text-lg font-semibold">Assignments</h2>
      {items.length === 0 ? <p className="text-sm text-zinc-600">No assignments yet.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-zinc-500">
              <tr><th className="py-1 pr-3">Set</th><th className="pr-3">Trainer&apos;s top fault</th>
                <th className="pr-3">Our top fault</th><th>Grade</th></tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.assignment_id} className="border-t border-zinc-200 align-top">
                  <td className="py-2 pr-3">
                    <p className="font-medium">{a.lift_label} · {a.status_label}</p>
                    <p className="break-all text-xs text-zinc-500">{a.trainer_email ?? "Deleted account"}</p>
                    <p className="text-xs text-zinc-500">Assigned {formatDate(a.assigned_at)}</p>
                    <Link href={`/admin/analyses/${a.analysis_id}`} className="text-xs underline">View analysis</Link>
                  </td>
                  <td className="py-2 pr-3">{a.trainer_answer?.name ?? "—"}</td>
                  <td className="py-2 pr-3">{a.our_fault.name}</td>
                  <td className="py-2">{a.verdict_label ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** US-22: send trainers a random sample to grade blind, and follow their grades. */
export function AdminGrading({ token, onForbidden }: { token: string | null; onForbidden: () => void }) {
  const [trainers, setTrainers] = useState<Trainer[] | null>(null);
  const [items, setItems] = useState<AdminGradingAssignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const failed = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 403) onForbidden();
    else setError("Couldn't load trainer grading. Please refresh to try again.");
  }, [onForbidden]);

  const reload = useCallback(() => {
    api.gradingAssignments(token).then((r) => setItems(r.items)).catch(failed);
  }, [token, failed]);

  useEffect(() => {
    api.adminTrainers(token).then((r) => setTrainers(r.items)).catch(failed);
    reload();
  }, [token, failed, reload]);

  return (
    <div className="space-y-6">
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {trainers && trainers.length === 0 && (
        <p className="rounded-xl bg-zinc-100 p-4 text-sm">
          No trainer accounts yet. Set a user&apos;s app_metadata role to &quot;trainer&quot; in Supabase; they appear here
          after they sign in.
        </p>
      )}
      {trainers && trainers.length > 0 && <AssignSample trainers={trainers} token={token} onAssigned={reload} />}
      {items && <Assignments items={items} />}
    </div>
  );
}
