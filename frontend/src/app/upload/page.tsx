"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { UploadForm } from "@/components/UploadForm";
import { uploadVideo } from "@/lib/api";
import { isLift } from "@/lib/lifts";
import { getToken } from "@/lib/session";

function Upload() {
  const router = useRouter();
  const params = useSearchParams();
  const lift = params.get("lift");
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Check your form</h1>
      <UploadForm
        initialLift={isLift(lift) ? lift : null}
        initialGuideOpen={params.get("guide") === "1"}
        upload={(args) => uploadVideo({ ...args, token: getToken() })}
        onUploaded={(id) => router.push(`/results/${id}`)}
      />
    </div>
  );
}

export default function UploadPage() {
  return <Suspense><Upload /></Suspense>;
}
