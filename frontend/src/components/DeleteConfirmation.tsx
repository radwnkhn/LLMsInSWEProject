"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { ApiError } from "@/lib/api";

type Props = { kind: "upload" | "account"; onConfirm: () => Promise<void>; onClose: () => void };

export function DeleteConfirmation({ kind, onConfirm, onClose }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    cancel.current?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);

  async function confirm() {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't complete deletion. Check your connection and try again.");
      setPending(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      if (!pending) onClose();
    }
    if (event.key === "Tab") {
      const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (!first) event.preventDefault();
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}
        onKeyDown={onKeyDown} className="w-full max-w-md space-y-4 rounded-xl bg-white p-5 shadow-xl">
        <h2 id={titleId} className="text-xl font-bold">{kind === "account" ? "Delete your account?" : "Delete this upload?"}</h2>
        <p id={descriptionId} className="text-sm text-zinc-700">
          {kind === "account"
            ? "This permanently removes your account and all your uploads, videos, frames, measurements and AI feedback. This cannot be undone."
            : "This permanently removes this video, frames, measurements and AI feedback, including any retried analyses. This cannot be undone."}
        </p>
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
        <div className="flex flex-wrap justify-end gap-3">
          <button ref={cancel} type="button" disabled={pending} onClick={onClose}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-semibold disabled:opacity-40">Cancel</button>
          <button type="button" disabled={pending} onClick={() => void confirm()}
            className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {pending ? "Deleting…" : kind === "account" ? "Delete account" : "Delete upload"}
          </button>
        </div>
      </div>
    </div>
  );
}
