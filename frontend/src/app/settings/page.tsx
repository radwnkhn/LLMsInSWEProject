"use client";

import { useRouter } from "next/navigation";

import { DeleteAccountForm } from "@/components/DeleteAccountForm";
import { api } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";

export default function SettingsPage() {
  const router = useRouter();
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Settings</h1>
      <DeleteAccountForm deleteAccount={() => api.deleteAccount(getToken())} onDeleted={() => {
        clearSession();
        router.replace("/login?deleted=1");
      }} />
    </div>
  );
}
