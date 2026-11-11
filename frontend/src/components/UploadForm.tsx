"use client";

import { useId, useState, type FormEvent } from "react";

import { FilmingGuide } from "@/components/FilmingGuide";
import { AnalysisProgress } from "@/components/AnalysisProgress";
import { LiftPicker } from "@/components/LiftPicker";
import { ApiError } from "@/lib/api";
import type { Lift } from "@/lib/types";
import { ACCEPT, getVideoDuration, validateVideoFile } from "@/lib/videoFile";

export type UploadArgs = { file: File; lift: Lift; note: string; onProgress: (percent: number) => void };

type Props = {
  upload: (args: UploadArgs) => Promise<{ analysis_id: string }>;
  readDuration?: (file: File) => Promise<number>;
  onUploaded?: (analysisId: string) => void;
  initialLift?: Lift | null;
  initialGuideOpen?: boolean;
};

const NOTE_LIMIT = 300;

function isRetryable(err: unknown) {
  return !(err instanceof ApiError) || err.status === 0 || err.status >= 500;
}

export function UploadForm({ upload, readDuration = getVideoDuration, onUploaded, initialLift = null, initialGuideOpen = false }: Props) {
  const [lift, setLift] = useState<Lift | null>(initialLift);
  const [guideOpen, setGuideOpen] = useState(Boolean(initialLift && initialGuideOpen));
  const [guideSeen, setGuideSeen] = useState(Boolean(initialLift && initialGuideOpen));
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadError, setUploadError] = useState<{ message: string; retryable: boolean } | null>(null);
  const fileHintId = useId();
  const noteHintId = useId();

  function chooseLift(next: Lift) {
    setLift(next);
    if (!guideSeen) {
      setGuideOpen(true);
      setGuideSeen(true);
    }
  }

  async function chooseFile(picked: File | undefined) {
    setFile(null);
    setFileError(null);
    setUploadError(null);
    if (!picked) return;
    const typeError = validateVideoFile(picked, null);
    if (typeError) {
      setFileError(typeError);
      return;
    }
    setChecking(true);
    let duration: number | null = null;
    try {
      duration = await readDuration(picked);
    } catch {
      duration = null; // the server checks the length too
    }
    setChecking(false);
    const error = validateVideoFile(picked, duration);
    if (error) setFileError(error);
    else setFile(picked);
  }

  async function start() {
    if (!file || !lift) return;
    setUploading(true);
    setUploadError(null);
    setProgress(0);
    try {
      const res = await upload({ file, lift, note, onProgress: setProgress });
      onUploaded?.(res.analysis_id);
    } catch (err) {
      const retryable = isRetryable(err);
      setUploadError({
        message: retryable ? "Upload failed. Check your connection and try again." : (err as ApiError).detail,
        retryable,
      });
    } finally {
      setUploading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void start();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <LiftPicker value={lift} onChange={chooseLift} />
      <button type="button" disabled={!lift} onClick={() => setGuideOpen(true)}
        className="text-sm font-medium text-zinc-700 underline disabled:no-underline disabled:opacity-40">
        Filming tips
      </button>
      {guideOpen && lift && <FilmingGuide lift={lift} onClose={() => setGuideOpen(false)} />}

      <div>
        <label className="block">
          <span className="text-sm font-medium">Video of your set</span>
          <input type="file" accept={ACCEPT} aria-describedby={fileHintId} onChange={(e) => void chooseFile(e.target.files?.[0])}
            className="mt-1 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-100 file:px-3 file:py-2" />
        </label>
        <p id={fileHintId} className="mt-1 text-xs text-zinc-500">MP4 or MOV, up to 60 seconds and 200 MB.</p>
      </div>
      {fileError && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{fileError}</p>}

      <div>
        <label className="block">
          <span className="text-sm font-medium">Anything we should know? (optional)</span>
          <textarea maxLength={NOTE_LIMIT} rows={2} value={note} onChange={(e) => setNote(e.target.value)} aria-describedby={noteHintId}
            placeholder="e.g. last two reps felt slow" className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm" />
        </label>
        <p id={noteHintId} className="text-right text-xs text-zinc-500">{note.length}/{NOTE_LIMIT}</p>
      </div>

      {uploading && (
        <div className="space-y-1">
          <AnalysisProgress stage="uploading" />
          <div role="progressbar" aria-label="Upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}
            className="h-2 overflow-hidden rounded-full bg-zinc-200">
            <div className="h-full bg-zinc-900 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-sm">{progress}%</p>
        </div>
      )}
      {uploadError && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>{uploadError.message}</span>
          {uploadError.retryable && (
            <button type="button" onClick={() => void start()} className="rounded-md bg-red-700 px-3 py-1 font-semibold text-white">
              Retry
            </button>
          )}
        </div>
      )}

      <button type="submit" disabled={!lift || !file || checking || uploading}
        className="w-full rounded-lg bg-zinc-900 px-4 py-3 font-semibold text-white disabled:opacity-40">
        Upload
      </button>
    </form>
  );
}
