import type { Lift } from "@/lib/types";

export const LIFTS: { id: Lift; label: string; noun: string }[] = [
  { id: "squat", label: "Squat", noun: "squat" },
  { id: "deadlift", label: "Deadlift", noun: "deadlift" },
  { id: "bench_press", label: "Bench Press", noun: "bench press" },
];

export function liftLabel(id: Lift): string {
  return LIFTS.find((l) => l.id === id)?.label ?? id;
}

export function liftNoun(id: Lift): string {
  return LIFTS.find((l) => l.id === id)?.noun ?? id;
}

export function isLift(value: string | null | undefined): value is Lift {
  return LIFTS.some((l) => l.id === value);
}
