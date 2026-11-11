"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);
  useEffect(() => setLoggedIn(Boolean(getToken())), [pathname]);

  async function logout() {
    const token = getToken();
    clearSession();
    setLoggedIn(false);
    if (token) await api.logout(token).catch(() => {});
    router.push("/login");
  }

  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
      {/* Don't cache an unauthenticated redirect before the user signs in. */}
      <Link href="/upload" prefetch={false} className="text-lg font-bold">Alibi</Link>
      {loggedIn && (
        <div className="flex flex-wrap items-center gap-3 text-sm sm:gap-4">
          <Link href="/upload">Upload</Link>
          <Link href="/history">History</Link>
          <Link href="/settings">Settings</Link>
          <button type="button" onClick={() => void logout()} className="font-medium underline">Log out</button>
        </div>
      )}
    </nav>
  );
}
