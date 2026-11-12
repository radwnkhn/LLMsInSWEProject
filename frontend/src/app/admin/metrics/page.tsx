"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AdminForbidden } from "@/components/AdminForbidden";
import { MetricsDashboard } from "@/components/MetricsDashboard";
import { getToken } from "@/lib/session";

export default function AdminMetricsPage() {
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [forbidden, setForbidden] = useState(false);
  const onForbidden = useCallback(() => setForbidden(true), []);
  useEffect(() => setToken(getToken()), []);
  if (forbidden) return <AdminForbidden />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">Hypothesis metrics</h1>
        <Link href="/admin" className="text-sm underline">Analyses</Link>
      </div>
      {token !== undefined && <MetricsDashboard token={token} onForbidden={onForbidden} />}
    </div>
  );
}
