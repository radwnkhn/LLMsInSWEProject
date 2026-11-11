import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("US-21 deletion requests", () => {
  it("us21_upload_delete_sends_authenticated_explicit_confirmation", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await api.deleteUpload("u/1", "session-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/uploads/u%2F1"), expect.objectContaining({
      method: "DELETE", body: JSON.stringify({ confirmed: true }),
      headers: { "Content-Type": "application/json", Authorization: "Bearer session-token" },
    }));
  });

  it("us21_account_delete_targets_the_current_account_only", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await api.deleteAccount("session-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/account"), expect.objectContaining({
      method: "DELETE", body: JSON.stringify({ confirmed: true }),
    }));
  });
});
