"use client";

import { formatTime } from "@/lib/format";
import type { AnnotatedFrameData } from "@/lib/types";

export function AnnotatedFrame({ frame, onPlayFrom }: { frame: AnnotatedFrameData; onPlayFrom: (seconds: number) => void }) {
  const time = formatTime(frame.timestamp);
  return (
    <figure className="space-y-2">
      <button type="button" aria-label={`Play rep ${frame.rep} from the start`} data-rep-start={frame.rep_start_time}
        onClick={() => onPlayFrom(frame.rep_start_time)} className="block w-full overflow-hidden rounded-xl border border-zinc-200">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={frame.image_url} alt={`Rep ${frame.rep} at ${time} with the measurement ${frame.label}`} className="h-auto w-full" />
      </button>
      <figcaption className="text-sm text-zinc-600">{`Rep ${frame.rep} · ${time} · ${frame.label}`}</figcaption>
    </figure>
  );
}
