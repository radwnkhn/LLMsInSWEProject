"use client";

import { LIFTS } from "@/lib/lifts";
import type { Lift } from "@/lib/types";

export function LiftPicker({ value, onChange }: { value: Lift | null; onChange: (lift: Lift) => void }) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">Which lift?</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {LIFTS.map((l) => (
          <label key={l.id}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${value === l.id ? "border-zinc-900 bg-zinc-100" : "border-zinc-300"}`}>
            <input type="radio" name="lift" value={l.id} checked={value === l.id} onChange={() => onChange(l.id)}
              className="accent-zinc-900" />
            {l.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
