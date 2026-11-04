"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ResultsView } from "@/components/ResultsView";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AnalysisResult } from "@/lib/types";

const POLL_MS = 1500;

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.analysis(id, getToken());
      setResult(r);
      return r.status === "queued" || r.status === "processing";
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push(`/login?next=/results/${id}`);
      else setError(err instanceof ApiError && err.status === 404 ? "We couldn't find that result." : "Couldn't load this result.");
      return false;
    }
  }, [id, router]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const tick = async () => {
      if (await load() && !stopped) timer = setTimeout(tick, POLL_MS);
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [load]);

  if (error) return <p role="alert">{error}</p>;
  if (!result) return <p role="status" className="text-zinc-600">Loading…</p>;
  return (
    <ResultsView
      result={result}
      onFeedback={async (answer) => { await api.sendFeedback(id, answer, getToken()); }}
      onPreviousCueAnswer={async (prevId, tried) => { await api.sendFeedback(prevId, { tried_cue: tried }, getToken()); }}
    />
  );
}
