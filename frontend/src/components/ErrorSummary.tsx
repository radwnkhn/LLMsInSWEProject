const LABELS: Record<string, string> = {
  invalid_json: "Reply wasn't valid JSON",
  schema: "Didn't match the JSON schema",
  lift_mismatch: "Wrong lift",
  camera_angle_mismatch: "Wrong camera angle",
  rep_count: "Wrong rep count",
  unknown_fault: "Fault not on the list",
  not_measurable: "Fault not measurable from this video",
  fault_not_confirmed: "Fault not confirmed by measurements",
  rep_out_of_range: "Cited a rep that doesn't exist",
  number_mismatch: "Number doesn't match the measurements",
  safety_order: "Safety fault not put first",
  missing_cue: "Missing cue",
  cue_too_long: "Cue longer than 12 words",
  medical_language: "Medical or injury language",
  missing_referral: "No referral after pain was mentioned",
  llm_error: "LLM request failed",
};

export function ErrorSummary({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">Validator errors</h2>
      {entries.length === 0 ? (
        <p className="text-sm text-zinc-600">No validator errors yet.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 text-sm">
          {entries.map(([code, count]) => (
            <li key={code} className="flex justify-between px-3 py-2">
              <span>{LABELS[code] ?? code}</span>
              <span className="font-semibold">{count}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
