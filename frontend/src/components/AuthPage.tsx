"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { AuthForm } from "@/components/AuthForm";
import { api } from "@/lib/api";
import { setSession } from "@/lib/session";
import type { Session } from "@/lib/types";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const target = next && next.startsWith("/") && !next.startsWith("//") ? next : "/upload";

  function done(session: Session) {
    setSession(session.access_token);
    router.push(target);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{mode === "signup" ? "Create your account" : "Log in"}</h1>
      {mode === "login" && params.get("deleted") === "1" && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Your account was deleted.</p>}
      <AuthForm mode={mode} submit={mode === "signup" ? api.signup : api.login} onSuccess={done} />
      <p className="text-sm text-zinc-600">
        {mode === "signup"
          ? <>Already have an account? <Link href="/login" className="underline">Log in</Link></>
          : <>New here? <Link href="/signup" className="underline">Create an account</Link></>}
      </p>
    </div>
  );
}
