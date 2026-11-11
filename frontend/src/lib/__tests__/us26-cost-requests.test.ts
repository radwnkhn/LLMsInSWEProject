import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import * as format from "@/lib/format";

afterEach(() => vi.unstubAllGlobals());

type CostFormat = { formatCost: (dollars: number | null) => string; formatTokens: (n: number) => string };
const { formatCost, formatTokens } = format as unknown as CostFormat;

describe("US-26 cost requests and formatting", () => {
  it("us26_cost_summary_is_read_for_the_chosen_dates_with_the_admin_session", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ total_cost: 0 }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await api.adminCosts("2026-11-01", "2026-11-10", "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/costs\?start=2026-11-01&end=2026-11-10$/),
      expect.objectContaining({ method: "GET", headers: { Authorization: "Bearer admin-token" } }));
  });

  it("us26_cost_summary_without_dates_uses_the_server_default_range", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ total_cost: 0 }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await api.adminCosts(null, null, "admin-token");
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/costs$/), expect.anything());
  });

  it("us26_costs_are_shown_in_dollars_and_unknown_costs_say_so", () => {
    expect(formatCost(null)).toBe("Unknown cost");
    expect(formatCost(0)).toBe("$0.00");
    expect(formatCost(0.007012)).toBe("$0.0070");
    expect(formatCost(0.000035)).toBe("<$0.0001"); // a real but tiny cost must not look free
    expect(formatCost(7)).toBe("$7.00");
    expect(formatCost(1234.5)).toBe("$1,234.50");
    expect(formatTokens(4003)).toBe("4,003");
  });
});
