"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AdminFaultList } from "@/components/AdminFaultList";
import { AdminForbidden } from "@/components/AdminForbidden";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AdminFaultLift } from "@/lib/types";

export default function AdminFaultsPage() {
  const [lifts, setLifts] = useState<AdminFaultLift[] | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    const t = getToken();
    setToken(t);
    api.adminFaults(t)
      .then((r) => setLifts(r.lifts))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) setForbidden(true);
        else setError("Couldn't load the fault list. Please refresh to try again.");
      });
  }, []);
  if (forbidden) return <AdminForbidden />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">Fault list</h1>
        <Link href="/admin" className="text-sm underline">Analyses</Link>
      </div>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {lifts && <AdminFaultList initial={lifts} token={token} />}
    </div>
  );
}
