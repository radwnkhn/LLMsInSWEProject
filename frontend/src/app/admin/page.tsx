"use client";

import { useEffect, useState } from "react";

import { AdminAnalysesTable } from "@/components/AdminAnalysesTable";
import { AdminForbidden } from "@/components/AdminForbidden";
import { ErrorSummary } from "@/components/ErrorSummary";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AdminRow } from "@/lib/types";

export default function AdminPage() {
  const [rows, setRows] = useState<AdminRow[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [forbidden, setForbidden] = useState(false);
  useEffect(() => {
    const token = getToken();
    Promise.all([api.adminAnalyses(token), api.adminErrors(token)])
      .then(([a, e]) => { setRows(a.items); setCounts(e.counts); })
      .catch((err) => { if (err instanceof ApiError && err.status === 403) setForbidden(true); });
  }, []);
  if (forbidden) return <AdminForbidden />;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Analyses</h1>
      {rows && <AdminAnalysesTable items={rows} />}
      <ErrorSummary counts={counts} />
    </div>
  );
}
