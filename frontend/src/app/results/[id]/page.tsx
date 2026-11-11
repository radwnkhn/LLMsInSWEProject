"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ResultsView } from "@/components/ResultsView";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { AnalysisResult } from "@/lib/types";

const POLL_MS = 1500;
const REQUEST_TIMEOUT_MS = 30_000;

// removed: the API's explanation when a moderator removed this upload (US-27).
type PageState = { id: string; result: AnalysisResult | null; error: string | null; removed?: string };

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<PageState>({ id, result: null, error: null });
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController;
    let stopped = false;
    setState({ id, result: null, error: null });
    const tick = async () => {
      controller = new AbortController();
      timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      try {
        const result = await api.analysis(id, getToken(), controller.signal);
        if (stopped) return;
        setState({ id, result, error: null });
        if (result.status === "queued" || result.status === "processing") timer = setTimeout(tick, POLL_MS);
      } catch (err) {
        if (stopped) return;
        if (err instanceof ApiError && err.status === 401) router.push(`/login?next=/results/${id}`);
        else if (err instanceof ApiError && err.status === 410) setState({ id, result: null, error: null, removed: err.detail });
        else setState({ id, result: null, error: err instanceof ApiError && err.status === 404
          ? "We couldn't find that result." : "Couldn't load this result. Check your connection and try again." });
      } finally {
        clearTimeout(timeout);
      }
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
      clearTimeout(timeout);
      controller?.abort();
    };
  }, [id, router, reload]);

  const { result, error, removed } = state.id === id ? state : { result: null, error: null, removed: undefined };
  if (removed) return (
    <div className="space-y-3 rounded-xl bg-zinc-100 p-4">
      <h1 className="text-lg font-semibold">This upload was removed by a moderator</h1>
      <p className="text-zinc-700">{removed.replace(/^This upload was removed by a moderator\.?\s*/, "")}</p>
      <Link href="/history" className="inline-block underline">Back to history</Link>
    </div>
  );
  if (error) return (
    <div role="alert" className="space-y-3 rounded-xl bg-red-50 p-4 text-red-800">
      <p>{error}</p>
      <button type="button" onClick={() => setReload((value) => value + 1)}
        className="rounded-lg bg-red-800 px-4 py-2 font-semibold text-white">Retry</button>
    </div>
  );
  if (!result) return <p role="status" className="text-zinc-600">Loading…</p>;
  return (
    <ResultsView
      key={id}
      result={result}
      onRetry={async () => {
        try {
          const retried = await api.retryAnalysis(id, getToken());
          router.replace(`/results/${retried.analysis_id}`);
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) router.push(`/login?next=/results/${id}`);
          throw err;
        }
      }}
      onFeedback={async (answer) => { await api.sendFeedback(id, answer, getToken()); }}
      onPreviousCueAnswer={async (prevId, tried) => { await api.sendFeedback(prevId, { tried_cue: tried }, getToken()); }}
    />
  );
}
