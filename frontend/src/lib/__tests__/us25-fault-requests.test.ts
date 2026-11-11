import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("US-25 fault list requests", () => {
  it("us25_fault_list_is_read_with_the_admin_session", async () => {
    const fetch = vi.fn().mockResolvedValue(json({ lifts: [] }));
    vi.stubGlobal("fetch", fetch);
    expect(await api.adminFaults("admin-token")).toEqual({ lifts: [] });
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/faults$/), expect.objectContaining({
      method: "GET", headers: { Authorization: "Bearer admin-token" },
    }));
  });

  it("us25_edit_sends_only_the_name_and_short_description", async () => {
    const fetch = vi.fn().mockResolvedValue(json({ id: "knee_cave" }));
    vi.stubGlobal("fetch", fetch);
    await api.updateFault("squat", "knee_cave", { name: "Knees collapse", short_name: "knee collapse" }, "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/faults\/squat\/knee_cave$/), expect.objectContaining({
      method: "PATCH", body: JSON.stringify({ name: "Knees collapse", short_name: "knee collapse" }),
    }));
  });

  it("us25_disable_sends_enabled_false", async () => {
    const fetch = vi.fn().mockResolvedValue(json({ id: "knee_cave", enabled: false }));
    vi.stubGlobal("fetch", fetch);
    await api.updateFault("squat", "knee cave/x", { enabled: false }, "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/faults\/squat\/knee%20cave%2Fx$/),
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ enabled: false }) }));
  });

  it("us25_add_posts_the_new_fault_and_surfaces_the_rejection_reason", async () => {
    const fault = { lift: "squat" as const, id: "knees_stay_bent", name: "Knees stay bent", short_name: "knee bend",
      category: "technique" as const, metric: "knee_angle_min_deg", threshold: 179, direction: "below" as const };
    const fetch = vi.fn().mockResolvedValue(json({ detail: "squat already has a fault with ID 'knees_stay_bent'" }, 409));
    vi.stubGlobal("fetch", fetch);
    await expect(api.addFault(fault, "admin-token")).rejects.toMatchObject({
      status: 409, detail: "squat already has a fault with ID 'knees_stay_bent'" });
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/faults$/), expect.objectContaining({
      method: "POST", body: JSON.stringify(fault) }));
  });
});
