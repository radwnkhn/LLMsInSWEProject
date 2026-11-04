import { Suspense } from "react";

import { AuthPage } from "@/components/AuthPage";

export default function LoginPage() {
  return <Suspense><AuthPage mode="login" /></Suspense>;
}
