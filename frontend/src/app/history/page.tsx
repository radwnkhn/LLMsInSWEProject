"use client";

import { useEffect, useState } from "react";

import { HistoryList } from "@/components/HistoryList";
import { api } from "@/lib/api";
import { getToken } from "@/lib/session";
import type { HistoryItem } from "@/lib/types";

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    api.history(getToken()).then((r) => setItems(r.items)).catch(() => setError(true));
  }, []);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Your uploads</h1>
      {error && <p role="alert">Couldn&apos;t load your history.</p>}
      {items && <HistoryList items={items} />}
    </div>
  );
}
