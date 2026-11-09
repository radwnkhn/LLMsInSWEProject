import { Suspense } from "react";

import { AuthPage } from "@/components/AuthPage";

export default function SignupPage() {
  return <Suspense><AuthPage mode="signup" /></Suspense>;
}
