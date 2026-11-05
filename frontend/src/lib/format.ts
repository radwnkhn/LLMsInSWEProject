/** Seconds as m:ss.t, e.g. 6.67 -> "0:06.7". */
export function formatTime(seconds: number): string {
  const tenths = Math.round(seconds * 10) / 10;
  const minutes = Math.floor(tenths / 60);
  const rest = tenths - minutes * 60;
  return `${minutes}:${rest.toFixed(1).padStart(4, "0")}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
