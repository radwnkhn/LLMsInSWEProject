export const SESSION_COOKIE = "alibi_session";
const WEEK = 60 * 60 * 24 * 7;

export function setSession(token: string): void {
  document.cookie = `${SESSION_COOKIE}=${encodeURIComponent(token)}; path=/; max-age=${WEEK}; samesite=lax`;
}

export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${SESSION_COOKIE}=`));
  const value = match ? decodeURIComponent(match.slice(SESSION_COOKIE.length + 1)) : "";
  return value || null;
}

export function clearSession(): void {
  document.cookie = `${SESSION_COOKIE}=; path=/; max-age=0; samesite=lax`;
}

/** Pages that need a logged-in user. */
export function isProtectedPath(path: string): boolean {
  return /^\/(upload|history|results|admin)(\/|$)/.test(path);
}
