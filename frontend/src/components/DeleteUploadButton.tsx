"use client";

import { useState } from "react";

import { DeleteConfirmation } from "@/components/DeleteConfirmation";

export function DeleteUploadButton({ uploadId, onDelete }: { uploadId: string; onDelete: (id: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="mb-3 ml-3 text-sm font-medium text-red-700 underline">
        Delete upload
      </button>
      {open && <DeleteConfirmation kind="upload" onConfirm={() => onDelete(uploadId)} onClose={() => setOpen(false)} />}
    </>
  );
}
