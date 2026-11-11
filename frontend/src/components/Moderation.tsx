"use client";

import Link from "next/link";
import { useId, useState, type FormEvent } from "react";

import { DeleteConfirmation } from "@/components/DeleteConfirmation";
import { formatDate, formatDay } from "@/lib/format";
import { LIFTS } from "@/lib/lifts";
import type { AdminUpload, ModerationEntry, RemovalReason, UsageReport } from "@/lib/types";

const REASONS: [RemovalReason, string][] = [["off_topic", "Off-topic"], ["inappropriate", "Inappropriate"], ["other", "Other"]];
const MAX_NOTE = 200;
const field = "rounded-lg border border-zinc-300 px-2 py-1";

/** US-27: sign-ups and uploads per day for the chosen range. */
export function UsageSection({ usage, start, end, onRange }: {
  usage: UsageReport | null; start: string; end: string; onRange: (start: string, end: string) => void;
}) {
  const [from, setFrom] = useState(start);
  const [to, setTo] = useState(end);
  const [shown, setShown] = useState({ start, end });
  const fromId = useId();
  const toId = useId();
  // Follow the range the server settled on (its default on first load).
  if (shown.start !== start || shown.end !== end) {
    setShown({ start, end });
    setFrom(start);
    setTo(end);
  }

  function show(e: FormEvent) {
    e.preventDefault();
    onRange(from, to);
  }

  return (
    <section aria-label="Sign-ups and uploads" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="text-lg font-semibold">Sign-ups and uploads</h2>
      <form onSubmit={show} className="flex flex-wrap items-end gap-3 text-sm">
        <div>
          <label htmlFor={fromId} className="block">From</label>
          <input id={fromId} type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={field} />
        </div>
        <div>
          <label htmlFor={toId} className="block">To</label>
          <input id={toId} type="date" value={to} onChange={(e) => setTo(e.target.value)} className={field} />
        </div>
        <button type="submit" className="rounded-lg border border-zinc-300 px-3 py-1 font-medium">Show</button>
      </form>
      {usage && (
        <>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-zinc-500">Total sign-ups</dt><dd className="text-lg font-semibold">{usage.totals.signups}</dd></div>
            <div><dt className="text-zinc-500">Total uploads</dt><dd className="text-lg font-semibold">{usage.totals.uploads}</dd></div>
          </dl>
          <p className="text-xs text-zinc-500">
            {usage.removals === 1 ? "1 upload" : `${usage.removals} uploads`} removed by moderators in this range.
            Days are in UTC.
          </p>
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-zinc-500"><tr><th className="py-1 pr-3">Day</th><th className="pr-3">Sign-ups</th><th>Uploads</th></tr></thead>
              <tbody>
                {[...usage.days].reverse().map((d) => ( // newest day first
                  <tr key={d.date} className="border-t border-zinc-100">
                    <td className="py-1 pr-3">{formatDay(d.date)}</td><td className="pr-3">{d.signups}</td><td>{d.uploads}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function RemoveDialog({ upload, onRemove, onClose }: {
  upload: AdminUpload; onRemove: (reason: RemovalReason, note: string | null) => Promise<void>; onClose: () => void;
}) {
  const [reason, setReason] = useState<RemovalReason | null>(null);
  const [note, setNote] = useState("");
  const noteId = useId();
  return (
    <DeleteConfirmation kind="upload" title="Remove this upload?" confirmLabel="Remove upload" pendingLabel="Removing…"
      description={`This permanently deletes ${upload.user_email}'s ${upload.lift_label.toLowerCase()} video, its analyses and AI feedback. The owner will see that a moderator removed it.`}
      confirmDisabled={reason === null}
      onConfirm={() => onRemove(reason as RemovalReason, reason === "other" && note.trim() ? note.trim() : null)}
      onClose={onClose}>
      <fieldset className="space-y-2 text-sm">
        <legend className="font-semibold">Reason</legend>
        {REASONS.map(([value, label]) => (
          <label key={value} className="flex items-center gap-2">
            <input type="radio" name="reason" value={value} checked={reason === value} onChange={() => setReason(value)} />
            {label}
          </label>
        ))}
        {reason === "other" && (
          <div>
            <label htmlFor={noteId} className="block">Note (optional)</label>
            <textarea id={noteId} value={note} maxLength={MAX_NOTE} onChange={(e) => setNote(e.target.value)}
              rows={2} className={`w-full ${field}`} />
          </div>
        )}
      </fieldset>
    </DeleteConfirmation>
  );
}

/** US-27: every upload in the range, filterable by lift, each linked to its analysis and removable. */
export function UploadsSection({ uploads, lift, onLift, onRemove }: {
  uploads: AdminUpload[] | null; lift: string; onLift: (lift: string) => void;
  onRemove: (upload: AdminUpload, reason: RemovalReason, note: string | null) => Promise<void>;
}) {
  const [removing, setRemoving] = useState<AdminUpload | null>(null);
  const liftId = useId();
  return (
    <section aria-label="Uploads" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-lg font-semibold">Uploads</h2>
        <div className="text-sm">
          <label htmlFor={liftId} className="mr-2">Lift</label>
          <select id={liftId} value={lift} onChange={(e) => onLift(e.target.value)} className={field}>
            <option value="">All</option>
            {LIFTS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </div>
      </div>
      {uploads && uploads.length === 0 && <p className="text-sm text-zinc-600">No uploads in this range.</p>}
      {uploads && uploads.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-500"><tr><th className="py-1 pr-3">Upload</th><th className="pr-3">Owner</th><th /></tr></thead>
          <tbody>
            {uploads.map((u) => (
              <tr key={u.upload_id} className="border-t border-zinc-200 align-top">
                <td className="py-2 pr-3">
                  <p className="font-medium">{u.lift_label}</p>
                  <p className="text-xs text-zinc-500">{formatDate(u.created_at)} · {u.status_label}</p>
                </td>
                <td className="py-2 pr-3 break-all">{u.user_email}</td>
                <td className="space-y-1 py-2 text-right">
                  {u.analysis_id && <Link href={`/admin/analyses/${u.analysis_id}`} className="block underline">Analysis</Link>}
                  <button type="button" onClick={() => setRemoving(u)}
                    className="rounded-lg border border-red-300 px-2 py-1 font-medium text-red-800">Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {removing && (
        <RemoveDialog upload={removing} onClose={() => setRemoving(null)}
          onRemove={(reason, note) => onRemove(removing, reason, note)} />
      )}
    </section>
  );
}

/** US-27: who removed what, when and why. */
export function ModerationLog({ entries }: { entries: ModerationEntry[] | null }) {
  return (
    <section aria-label="Moderation log" className="space-y-2">
      <h2 className="text-lg font-semibold">Moderation log</h2>
      {entries && entries.length === 0 && <p className="text-sm text-zinc-600">No uploads have been removed.</p>}
      {entries && entries.length > 0 && (
        <ul className="space-y-2 text-sm">
          {entries.map((m) => (
            <li key={m.id} className="rounded-lg border border-zinc-200 p-2">
              <p className="font-medium">
                {m.reason_label}{m.note ? `: ${m.note}` : ""}
              </p>
              <p className="text-xs text-zinc-600 break-all">
                {formatDate(m.removed_at)} · {m.removed_by_email ?? "Deleted account"} removed{" "}
                {m.owner_email ?? "a deleted account"}&apos;s {m.lift.replace("_", " ")} upload
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
