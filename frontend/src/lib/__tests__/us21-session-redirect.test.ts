import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { middleware } from "@/middleware";

describe("US-21 returning to a protected page after account deletion", () => {
  it("us21_redirect_keeps_the_browser_loopback_origin_instead_of_normalized_localhost", () => {
    // Next's local server can normalize request.url while preserving the browser's Host header.
    const request = new NextRequest("http://localhost:3124/results/deleted", { headers: { host: "127.0.0.1:3124" } });
    const location = new URL(middleware(request).headers.get("location")!);
    expect(location.origin).toBe("http://127.0.0.1:3124");
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/results/deleted");
  });

  it("us21_redirect_preserves_a_production_origin", () => {
    const request = new NextRequest("https://alibi.example/settings", { headers: { host: "alibi.example" } });
    expect(new URL(middleware(request).headers.get("location")!).origin).toBe("https://alibi.example");
  });
});
