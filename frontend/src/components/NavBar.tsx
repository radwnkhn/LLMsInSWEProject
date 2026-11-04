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
    <nav className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
      <Link href="/upload" className="text-lg font-bold">Alibi</Link>
      {loggedIn && (
        <div className="flex items-center gap-4 text-sm">
          <Link href="/upload">Upload</Link>
          <Link href="/history">History</Link>
          <button type="button" onClick={() => void logout()} className="font-medium underline">Log out</button>
        </div>
      )}
    </nav>
  );
}
