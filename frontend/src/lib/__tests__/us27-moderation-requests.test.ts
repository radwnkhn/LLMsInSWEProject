import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

type ModerationApi = {
  adminUsage: (start: string | null, end: string | null, token: string | null) => Promise<unknown>;
  adminUploads: (filters: { start?: string; end?: string; lift?: string }, token: string | null) => Promise<unknown>;
  removeUpload: (uploadId: string, reason: string, note: string | null, token: string | null) => Promise<unknown>;
  moderationLog: (token: string | null) => Promise<unknown>;
};
const moderation = api as unknown as ModerationApi;

function ok(body: unknown = {}) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
}

describe("US-27 moderation requests", () => {
  it("us27_usage_is_read_for_the_chosen_dates", async () => {
    const fetch = ok();
    vi.stubGlobal("fetch", fetch);
    await moderation.adminUsage("2026-11-01", "2026-11-03", "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/usage\?start=2026-11-01&end=2026-11-03$/),
      expect.objectContaining({ method: "GET", headers: { Authorization: "Bearer admin-token" } }));
  });

  it("us27_upload_list_sends_only_the_filters_that_are_set", async () => {
    const fetch = ok({ items: [] });
    vi.stubGlobal("fetch", fetch);
    await moderation.adminUploads({ lift: "squat", start: "2026-11-01" }, "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/uploads\?start=2026-11-01&lift=squat$/),
      expect.anything());
    await moderation.adminUploads({}, "admin-token");
    expect(fetch).toHaveBeenLastCalledWith(expect.stringMatching(/\/admin\/uploads$/), expect.anything());
  });

  it("us27_removal_sends_explicit_confirmation_and_the_reason", async () => {
    const fetch = ok();
    vi.stubGlobal("fetch", fetch);
    await moderation.removeUpload("u/1", "other", "Not a lift", "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/uploads\/u%2F1\/remove$/), expect.objectContaining({
      method: "POST", body: JSON.stringify({ confirmed: true, reason: "other", note: "Not a lift" }) }));
    await moderation.removeUpload("u2", "off_topic", null, "admin-token");
    expect(fetch).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({
      body: JSON.stringify({ confirmed: true, reason: "off_topic" }) }));
  });

  it("us27_moderation_log_is_read_with_the_admin_session", async () => {
    const fetch = ok({ items: [] });
    vi.stubGlobal("fetch", fetch);
    await moderation.moderationLog("admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/moderation-log$/), expect.anything());
  });
});
