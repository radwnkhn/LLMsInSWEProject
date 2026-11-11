"use client";

import { useId, useState, type FormEvent, type ReactElement } from "react";

import { ApiError, api } from "@/lib/api";
import type { AdminFault, AdminFaultLift, FaultCategory, FaultDirection, FaultEdit, Lift, NewFault } from "@/lib/types";

// The same limits the API enforces (backend/app/faults.py), checked here first for a quicker message.
const LIMITS = { name: ["Display name", 80], short_name: ["Short description", 40] } as const;

function textError(field: keyof typeof LIMITS, value: string): string | null {
  const [label, max] = LIMITS[field];
  if (!value.trim()) return `${label} is required`;
  if (value.trim().length > max) return `${label} must be ${max} characters or fewer`;
  return null;
}

function message(err: unknown): string {
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

function rule(f: AdminFault): string {
  const value = f.unit === "°" ? `${f.threshold}°` : String(f.threshold);
  return `${f.direction} ${value}`;
}

const input = "w-full rounded-lg border border-zinc-300 px-2 py-1";

/** A label tied to its control by id, so the control's accessible name is just the label. */
function Field({ label, className = "text-sm", children }: {
  label: string; className?: string; children: (id: string) => ReactElement;
}) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block">{label}</label>
      {children(id)}
    </div>
  );
}
const button = "rounded-lg border border-zinc-300 px-2 py-1 text-sm font-medium";

function EditFault({ fault, token, onSaved, onCancel }: {
  fault: AdminFault; token: string | null; onSaved: (f: AdminFault) => void; onCancel: () => void;
}) {
  const [name, setName] = useState(fault.name);
  const [shortName, setShortName] = useState(fault.short_name);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    const problem = textError("name", name) ?? textError("short_name", shortName);
    if (problem) return setError(problem);
    setSaving(true);
    try {
      onSaved(await api.updateFault(fault.lift, fault.id, { name: name.trim(), short_name: shortName.trim() }, token));
    } catch (err) {
      setError(message(err));
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(e) => void save(e)} className="space-y-2" noValidate>
      <Field label="Display name">{(id) => (
        <input id={id} className={input} value={name} onChange={(e) => setName(e.target.value)} />
      )}</Field>
      <Field label="Short description">{(id) => (
        <input id={id} className={input} value={shortName} onChange={(e) => setShortName(e.target.value)} />
      )}</Field>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={saving} className={`${button} bg-zinc-900 text-white`}>Save</button>
        <button type="button" onClick={onCancel} className={button}>Cancel</button>
      </div>
    </form>
  );
}

function FaultRow({ fault, token, onChange }: { fault: AdminFault; token: string | null; onChange: (f: AdminFault) => void }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      onChange(await api.updateFault(fault.lift, fault.id, { enabled: !fault.enabled } satisfies FaultEdit, token));
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className={`border-t border-zinc-200 align-top ${fault.enabled ? "" : "text-zinc-500"}`}>
      <td className="space-y-2 py-2 pr-3">
        {editing ? (
          <EditFault fault={fault} token={token} onCancel={() => setEditing(false)}
            onSaved={(f) => { setEditing(false); onChange(f); }} />
        ) : (
          <div>
            <p className="font-medium">{fault.name}</p>
            <p className="text-xs text-zinc-500">{fault.short_name}</p>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${fault.enabled
            ? "bg-green-100 text-green-800" : "bg-zinc-200 text-zinc-700"}`}>{fault.enabled ? "Enabled" : "Disabled"}</span>
          {!editing && <button type="button" onClick={() => setEditing(true)} className={button}>Edit</button>}
          <button type="button" onClick={() => void toggle()} disabled={busy} className={button}>
            {fault.enabled ? "Disable" : "Enable"}
          </button>
        </div>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </td>
      <td className="py-2 pr-3">
        <p>{fault.category === "safety" ? "Safety" : "Technique"}</p>
        <p className="text-xs text-zinc-500">Safety fault: {fault.safety ? "Yes" : "No"}</p>
      </td>
      <td className="py-2">
        <p>{fault.metric_label}</p>
        <p className="text-xs text-zinc-500">{rule(fault)}</p>
      </td>
    </tr>
  );
}

function LiftFaults({ group, token, onChange }: {
  group: AdminFaultLift; token: string | null; onChange: (f: AdminFault) => void;
}) {
  return (
    <section aria-label={`${group.lift_label} faults`} className="space-y-2">
      <h2 className="text-lg font-semibold">{group.lift_label}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-500">
            <tr><th className="py-1 pr-3">Fault</th><th className="pr-3">Category</th><th>Measurement</th></tr>
          </thead>
          <tbody>
            {group.faults.map((f) => <FaultRow key={f.id} fault={f} token={token} onChange={onChange} />)}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const EMPTY = { id: "", name: "", short_name: "", threshold: "" };

function AddFault({ lifts, token, onAdded }: { lifts: AdminFaultLift[]; token: string | null; onAdded: (f: AdminFault) => void }) {
  const [lift, setLift] = useState<Lift | undefined>(lifts[0]?.lift);
  const metrics = lifts.find((g) => g.lift === lift)?.metrics ?? [];
  const [metric, setMetric] = useState(metrics[0]?.metric ?? "");
  const [category, setCategory] = useState<FaultCategory>("technique");
  const [direction, setDirection] = useState<FaultDirection>("above");
  const [fields, setFields] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) => setFields({ ...fields, [key]: e.target.value });

  function chooseLift(next: string) {
    const group = lifts.find((g) => g.lift === next);
    setLift(group?.lift);
    setMetric(group?.metrics[0]?.metric ?? "");
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    const threshold = Number(fields.threshold);
    const problem = (!fields.id.trim() && "Fault ID is required") || textError("name", fields.name)
      || textError("short_name", fields.short_name)
      || ((fields.threshold.trim() === "" || !Number.isFinite(threshold)) && "Threshold must be a number") || null;
    if (problem) return setError(problem);
    if (!lift) return;
    const fault: NewFault = { lift, id: fields.id.trim(), name: fields.name.trim(), short_name: fields.short_name.trim(),
      category, metric, threshold, direction };
    setSaving(true);
    setError(null);
    try {
      onAdded(await api.addFault(fault, token));
      setFields(EMPTY);
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-label="Add a fault" className="space-y-3 rounded-xl border border-zinc-200 p-4">
      <h2 className="text-lg font-semibold">Add a fault</h2>
      <p className="text-sm text-zinc-600">
        New faults must use a measurement the app already computes, so every fault the AI reports can be checked.
      </p>
      <form onSubmit={(e) => void add(e)} className="grid gap-3 sm:grid-cols-2" noValidate>
        <Field label="Lift">{(id) => (
          <select id={id} className={input} value={lift} onChange={(e) => chooseLift(e.target.value)}>
            {lifts.map((g) => <option key={g.lift} value={g.lift}>{g.lift_label}</option>)}
          </select>
        )}</Field>
        <Field label="Measurement">{(id) => (
          <select id={id} className={input} value={metric} onChange={(e) => setMetric(e.target.value)}>
            {metrics.map((m) => <option key={m.metric} value={m.metric}>{m.label}</option>)}
          </select>
        )}</Field>
        <Field label="Fault ID">{(id) => (
          <input id={id} className={input} value={fields.id} onChange={set("id")} placeholder="e.g. knees_stay_bent" />
        )}</Field>
        <Field label="Display name">{(id) => (
          <input id={id} className={input} value={fields.name} onChange={set("name")} />
        )}</Field>
        <Field label="Short description">{(id) => (
          <input id={id} className={input} value={fields.short_name} onChange={set("short_name")} />
        )}</Field>
        <Field label="Category">{(id) => (
          <select id={id} className={input} value={category} onChange={(e) => setCategory(e.target.value as FaultCategory)}>
            <option value="technique">Technique</option>
            <option value="safety">Safety</option>
          </select>
        )}</Field>
        <Field label="Flag when the measurement is">{(id) => (
          <select id={id} className={input} value={direction} onChange={(e) => setDirection(e.target.value as FaultDirection)}>
            <option value="above">Above the threshold</option>
            <option value="below">Below the threshold</option>
          </select>
        )}</Field>
        <Field label="Threshold">{(id) => (
          <input id={id} className={input} type="number" step="any" inputMode="decimal" value={fields.threshold}
            onChange={set("threshold")} />
        )}</Field>
        {error && <p role="alert" className="text-sm text-red-700 sm:col-span-2">{error}</p>}
        <div className="sm:col-span-2">
          <button type="submit" disabled={saving} className={`${button} bg-zinc-900 text-white`}>Add fault</button>
        </div>
      </form>
    </section>
  );
}

export function AdminFaultList({ initial, token }: { initial: AdminFaultLift[]; token: string | null }) {
  const [lifts, setLifts] = useState(initial);

  function replaceFault(updated: AdminFault) {
    setLifts((groups) => groups.map((g) => g.lift !== updated.lift ? g
      : { ...g, faults: g.faults.map((f) => (f.id === updated.id ? updated : f)) }));
  }

  function addFault(added: AdminFault) {
    setLifts((groups) => groups.map((g) => (g.lift === added.lift ? { ...g, faults: [...g.faults, added] } : g)));
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-zinc-600">
        Disabled faults are no longer offered to the AI, and replies that cite them are sent back for correction.
        Changes apply to new analyses; earlier results keep the faults they reported.
      </p>
      {lifts.map((g) => <LiftFaults key={g.lift} group={g} token={token} onChange={replaceFault} />)}
      <AddFault lifts={lifts} token={token} onAdded={addFault} />
    </div>
  );
}
