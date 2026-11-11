"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AdminAnalysesTable } from "@/components/AdminAnalysesTable";
import { AdminForbidden } from "@/components/AdminForbidden";
import { CostSummary } from "@/components/CostSummary";
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
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">Analyses</h1>
        <Link href="/admin/faults" className="text-sm underline">Fault list</Link>
      </div>
      {rows && <CostSummary token={getToken()} />}
      {rows && <AdminAnalysesTable items={rows} />}
      <ErrorSummary counts={counts} />
    </div>
  );
}
