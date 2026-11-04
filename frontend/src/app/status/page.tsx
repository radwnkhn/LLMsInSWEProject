"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

/** Deployment check: can this frontend reach the backend? */
export default function StatusPage() {
  const [state, setState] = useState("checking…");
  useEffect(() => {
    api.health().then((r) => setState(r.status)).catch(() => setState("unreachable"));
  }, []);
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold">Status</h1>
      <p role="status">Backend: {state}</p>
    </div>
  );
}
