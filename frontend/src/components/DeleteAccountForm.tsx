"use client";

import { useState } from "react";

import { DeleteConfirmation } from "@/components/DeleteConfirmation";

export function DeleteAccountForm({ deleteAccount, onDeleted }: { deleteAccount: () => Promise<void>; onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="space-y-3 rounded-xl border border-red-200 p-4">
      <h2 className="text-lg font-semibold">Delete your account</h2>
      <p className="text-sm text-zinc-600">Permanently delete your account and everything you uploaded. You will be signed out on every session.</p>
      <button type="button" onClick={() => setOpen(true)} className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white">
        Delete account
      </button>
      {open && <DeleteConfirmation kind="account" onClose={() => setOpen(false)} onConfirm={async () => {
        await deleteAccount();
        onDeleted();
      }} />}
    </section>
  );
}
