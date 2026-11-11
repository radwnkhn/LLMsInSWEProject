"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ComparisonView } from "@/components/ComparisonView";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AnalysisComparison } from "@/lib/types";

function Compare() {
  const params = useSearchParams();
  const router = useRouter();
  const first = params.get("first"), second = params.get("second");
  const key = `${first}:${second}`;
  const [reload, setReload] = useState(0);
  const [state, setState] = useState<{ key: string; data: AnalysisComparison | null; error: string | null }>({ key, data: null, error: null });
  useEffect(() => {
    if (!first || !second) return;
    let stopped = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    setState({ key, data: null, error: null });
    api.comparison(first, second, getToken(), controller.signal).then((data) => {
      if (!stopped) setState({ key, data, error: null });
    }).catch((err) => {
      if (stopped) return;
      if (err instanceof ApiError && err.status === 401) {
        router.push(`/login?next=${encodeURIComponent(`/compare?${new URLSearchParams({ first, second })}`)}`);
      } else setState({ key, data: null, error: err instanceof ApiError && err.status !== 0
        ? err.detail : "Couldn't load this comparison. Check your connection and try again." });
    }).finally(() => clearTimeout(timeout));
    return () => { stopped = true; clearTimeout(timeout); controller.abort(); };
  }, [first, second, key, reload, router]);

  const { data, error } = state.key === key ? state : { data: null, error: null };
  if (!first || !second || error) return (
    <div className="space-y-3">
      <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error ?? "Choose two uploads from your history."}</p>
      {first && second && <button type="button" onClick={() => setReload((value) => value + 1)}
        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white">Retry</button>}
      <Link href="/history" className="block text-sm underline">Back to history</Link>
    </div>
  );
  return data ? <ComparisonView comparison={data} /> : <p role="status">Loading comparison…</p>;
}

export default function ComparePage() {
  return <Suspense fallback={<p role="status">Loading comparison…</p>}><Compare /></Suspense>;
}
