"use client";

import { useId } from "react";

import { FILMING_GUIDES } from "@/lib/filming";
import { liftLabel } from "@/lib/lifts";
import type { Lift } from "@/lib/types";

export function FilmingGuide({ lift, onClose }: { lift: Lift; onClose: () => void }) {
  const titleId = useId();
  const guide = FILMING_GUIDES[lift];
  return (
    <div role="dialog" aria-modal="true" aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-3 sm:items-center">
      <div className="max-h-[92vh] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-5 text-zinc-900 shadow-xl">
        <h2 id={titleId} className="text-lg font-semibold">Filming tips: {liftLabel(lift)}</h2>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={guide.image} alt={guide.imageAlt} className="mt-3 h-auto w-full rounded-lg border border-zinc-200" />
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm">
          {guide.tips.map((tip) => <li key={tip}>{tip}</li>)}
        </ul>
        <button type="button" onClick={onClose}
          className="mt-4 w-full rounded-lg bg-zinc-900 px-4 py-2.5 font-semibold text-white">Got it</button>
      </div>
    </div>
  );
}
