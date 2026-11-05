"use client";

import { useId, useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import type { Session } from "@/lib/types";

type Props = {
  mode: "login" | "signup";
  submit: (email: string, password: string) => Promise<Session>;
  onSuccess: (session: Session) => void;
};

export function AuthForm({ mode, submit, onSuccess }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const signup = mode === "signup";
  const hintId = useId();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onSuccess(await submit(email, password));
    } catch (err) {
      setError(err instanceof ApiError && err.status >= 400 ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <label className="block">
        <span className="text-sm font-medium">Email</span>
        <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" />
      </label>
      <div>
        <label className="block">
          <span className="text-sm font-medium">Password</span>
          <input type="password" required minLength={signup ? 8 : undefined} aria-describedby={signup ? hintId : undefined}
            autoComplete={signup ? "new-password" : "current-password"} value={password}
            onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" />
        </label>
        {signup && <p id={hintId} className="mt-1 text-xs text-zinc-500">At least 8 characters</p>}
      </div>
      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button type="submit" disabled={busy}
        className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 font-semibold text-white disabled:opacity-50">
        {signup ? "Create account" : "Log in"}
      </button>
    </form>
  );
}
