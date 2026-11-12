"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { GradeAssignment } from "@/components/GradeAssignment";
import { TrainerForbidden } from "@/components/TrainerForbidden";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { TrainerAssignment } from "@/lib/types";

export default function GradeAssignmentPage() {
  const { id } = useParams<{ id: string }>();
  const [assignment, setAssignment] = useState<TrainerAssignment | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  useEffect(() => {
    const t = getToken();
    setToken(t);
    api.trainerAssignment(id, t).then(setAssignment).catch((err) => setStatus(err instanceof ApiError ? err.status : 0));
  }, [id]);
  if (status === 403) return <TrainerForbidden />;
  if (status) return <p role="alert">Couldn&apos;t load this set.</p>;
  if (!assignment) return <p role="status">Loading…</p>;
  return (
    <div className="space-y-4">
      <Link href="/grading" className="text-sm underline">All sets</Link>
      <GradeAssignment initial={assignment} token={token} />
    </div>
  );
}
