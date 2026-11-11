"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AdminForbidden } from "@/components/AdminForbidden";
import { ModerationLog, UploadsSection, UsageSection } from "@/components/Moderation";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AdminUpload, ModerationEntry, RemovalReason, UploadFilters, UsageReport } from "@/lib/types";

function filters(start: string, end: string, lift: string): UploadFilters {
  return { ...(start ? { start } : {}), ...(end ? { end } : {}), ...(lift ? { lift } : {}) };
}

/** US-27: sign-ups and uploads over time, the upload list with removal, and the moderation log. */
export default function ModerationPage() {
  const [token, setToken] = useState<string | null>(null);
  const [range, setRange] = useState({ start: "", end: "" });
  const [lift, setLift] = useState("");
  const [usage, setUsage] = useState<UsageReport | null>(null);
  const [uploads, setUploads] = useState<AdminUpload[] | null>(null);
  const [log, setLog] = useState<ModerationEntry[] | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 403) setForbidden(true);
    else setError(err instanceof ApiError ? err.detail : "Couldn't load usage and moderation. Please refresh to try again.");
  }, []);

  const load = useCallback(async (t: string | null, start: string | null, end: string | null, chosenLift: string) => {
    setError(null);
    try {
      const report = await api.adminUsage(start, end, t);
      setUsage(report);
      setRange({ start: report.start, end: report.end });
      setUploads((await api.adminUploads(filters(report.start, report.end, chosenLift), t)).items);
    } catch (err) {
      fail(err);
    }
  }, [fail]);

  useEffect(() => {
    const t = getToken();
    setToken(t);
    void load(t, null, null, "");
    api.moderationLog(t).then((r) => setLog(r.items)).catch(fail);
  }, [load, fail]);

  async function chooseLift(next: string) {
    setLift(next);
    try {
      setUploads((await api.adminUploads(filters(range.start, range.end, next), token)).items);
    } catch (err) {
      fail(err);
    }
  }

  async function remove(upload: AdminUpload, reason: RemovalReason, note: string | null) {
    const entry = await api.removeUpload(upload.upload_id, reason, note, token); // errors stay in the dialog
    setUploads((items) => (items ?? []).filter((u) => u.upload_id !== upload.upload_id));
    setLog((entries) => [entry, ...(entries ?? [])]);
    api.adminUsage(range.start, range.end, token).then(setUsage).catch(() => {});
  }

  if (forbidden) return <AdminForbidden />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">Usage and moderation</h1>
        <Link href="/admin" className="text-sm underline">Analyses</Link>
      </div>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <UsageSection usage={usage} start={range.start} end={range.end}
        onRange={(start, end) => void load(token, start || null, end || null, lift)} />
      <UploadsSection uploads={uploads} lift={lift} onLift={(next) => void chooseLift(next)} onRemove={remove} />
      <ModerationLog entries={log} />
    </div>
  );
}
