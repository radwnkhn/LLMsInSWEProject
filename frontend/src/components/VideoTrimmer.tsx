"use client";

import { useEffect, useRef, useState } from "react";

export type TrimRange = { start: number; end: number };
export function validTrim(trim: TrimRange | null, duration: number | null) {
  return trim === null || (duration !== null && Number.isFinite(trim.start) && Number.isFinite(trim.end)
    && trim.start >= 0 && trim.end > trim.start && trim.end <= duration);
}

export function VideoTrimmer({ file, duration, trim, onChange, disabled }: {
  file: File; duration: number | null; trim: TrimRange | null;
  onChange: (range: TrimRange | null) => void; disabled: boolean;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const previewing = useRef(false);
  const [source, setSource] = useState<string | undefined>();
  const [previewError, setPreviewError] = useState(false);
  useEffect(() => {
    if (typeof URL.createObjectURL !== "function") return;
    const objectURL = URL;
    const url = objectURL.createObjectURL(file);
    setSource(url);
    return () => objectURL.revokeObjectURL(url);
  }, [file]);
  const valid = validTrim(trim, duration);

  function change(range: TrimRange | null) {
    video.current?.pause();
    previewing.current = false;
    onChange(range);
  }

  async function preview() {
    if (!video.current || !trim || !valid) return;
    video.current.currentTime = trim.start;
    previewing.current = true;
    try {
      await video.current.play();
    } catch {
      previewing.current = false;
      setPreviewError(true);
    }
  }

  return (
    <section aria-label="Choose the part of your video to analyze" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="font-semibold">Preview your set</h2>
      <video ref={video} src={source} controls playsInline preload="metadata" aria-label="Video preview"
        className="max-h-72 w-full rounded-lg bg-black"
        onTimeUpdate={() => {
          if (previewing.current && trim && video.current && video.current.currentTime >= trim.end) {
            video.current.pause();
            previewing.current = false;
          }
        }} onError={() => setPreviewError(true)} />
      <p className="text-sm text-zinc-600">Optionally exclude setup, walking, or movements after your set. Your full video stays available.</p>
      {previewError && <p className="text-sm text-amber-800">This browser couldn’t preview the video. You can still upload the full video.</p>}
      {duration !== null && duration > 0 && Number.isFinite(duration) ? (
        <>
          <p className="text-sm" aria-live="polite">{trim
            ? `Selected: ${(trim.end - trim.start).toFixed(1)} seconds (${trim.start.toFixed(1)}–${trim.end.toFixed(1)}s)`
            : `Full video: ${duration.toFixed(1)} seconds`}</p>
          {!trim ? <button type="button" disabled={disabled} onClick={() => change({ start: 0, end: duration })}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium">Choose a segment</button> : (
            <fieldset disabled={disabled} className="space-y-3">
              <legend className="text-sm font-medium">Analysis segment</legend>
              <div className="relative h-2 overflow-hidden rounded bg-zinc-200" aria-hidden="true">
                <div className="absolute h-full bg-emerald-600" style={{ left: `${100 * trim.start / duration}%`, width: `${Math.max(0, 100 * (trim.end - trim.start) / duration)}%` }} />
              </div>
              <label className="block text-sm">Segment start
                <input type="range" min={0} max={duration} step={0.01} value={Number.isFinite(trim.start) ? trim.start : 0}
                  onChange={(e) => change({ ...trim, start: Number(e.target.value) })} className="block w-full accent-emerald-700" />
              </label>
              <label className="block text-sm">Start time (seconds)
                <input type="number" min={0} max={duration} step={0.01} value={Number.isFinite(trim.start) ? trim.start : ""}
                  onChange={(e) => change({ ...trim, start: e.target.valueAsNumber })} className="ml-2 w-24 rounded border p-1" />
              </label>
              <label className="block text-sm">Segment end
                <input type="range" min={0} max={duration} step={0.01} value={Number.isFinite(trim.end) ? trim.end : duration}
                  onChange={(e) => change({ ...trim, end: Number(e.target.value) })} className="block w-full accent-emerald-700" />
              </label>
              <label className="block text-sm">End time (seconds)
                <input type="number" min={0} max={duration} step={0.01} value={Number.isFinite(trim.end) ? trim.end : ""}
                  onChange={(e) => change({ ...trim, end: e.target.valueAsNumber })} className="ml-2 w-24 rounded border p-1" />
              </label>
              {!valid && <p role="alert" className="text-sm text-red-700">Choose a start and end within the video, with the end after the start.</p>}
              <div className="flex flex-wrap gap-3">
                <button type="button" disabled={!valid} onClick={() => void preview()} className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-40">Preview selection</button>
                <button type="button" onClick={() => change(null)} className="text-sm underline">Reset to full video</button>
              </div>
            </fieldset>
          )}
        </>
      ) : <p className="text-sm text-zinc-600">The duration couldn’t be read here. The full video will be checked after upload.</p>}
    </section>
  );
}
