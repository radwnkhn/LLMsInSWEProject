/** Seconds as m:ss.t, e.g. 6.67 -> "0:06.7". */
export function formatTime(seconds: number): string {
  const tenths = Math.round(seconds * 10) / 10;
  const minutes = Math.floor(tenths / 60);
  const rest = tenths - minutes * 60;
  return `${minutes}:${rest.toFixed(1).padStart(4, "0")}`;
}

/** US-26: dollars, with four decimals below $1 because one analysis usually costs a fraction of a cent. */
export function formatCost(dollars: number | null): string {
  if (dollars === null) return "Unknown cost";
  if (dollars === 0) return "$0.00";
  if (dollars < 0.0001) return "<$0.0001";
  if (dollars < 1) return `$${dollars.toFixed(4)}`;
  return dollars.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatTokens(count: number): string {
  return count.toLocaleString("en-US");
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
