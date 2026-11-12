import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";
import type { HypothesisMetric, MetricsReport } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, adminMetrics: vi.fn(), adminAnalyses: vi.fn(), adminErrors: vi.fn(),
    adminCosts: vi.fn() } };
});

// Loaded at run time so each test reports its own failure while the page doesn't exist yet.
const PAGE = "@/app/admin/metrics/page";
async function renderPage(path = PAGE) {
  const { default: Page } = (await import(/* @vite-ignore */ path)) as { default: ComponentType };
  render(<Page />);
}

const metric = (overrides: Partial<HypothesisMetric>): HypothesisMetric => ({
  key: "trainer_agreement", label: "Trainer agreement", value: 2 / 3, hits: 2, count: 3, basis: "3 graded sets",
  target: 0.8, fail_below: 0.6, status: "below_target", status_label: "Below target", ...overrides,
});

const REPORT: MetricsReport = {
  start: "2026-10-14", end: "2026-11-12", pending_returns: 1,
  metrics: [
    metric({}),
    metric({ key: "helpful_ratings", label: "Helpful ratings (4–5)", value: 0.75, hits: 3, count: 4, basis: "4 ratings",
      target: 0.7, fail_below: 0.5, status: "on_target", status_label: "On target" }),
    metric({ key: "cue_tried", label: "Cue tried", value: 0.25, hits: 1, count: 4, basis: "4 answers", target: 0.6,
      fail_below: 0.4, status: "failing", status_label: "Failing" }),
    metric({ key: "seven_day_return", label: "7-day return", value: null, hits: 0, count: 0, basis: "0 lifters",
      target: 0.5, fail_below: 0.3, status: "no_data", status_label: "No data" }),
  ],
};

function card(name: string) {
  return screen.findByRole("region", { name });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.adminMetrics).mockResolvedValue(structuredClone(REPORT));
});

describe("US-23 hypothesis metrics dashboard", () => {
  it("us23_shows_the_four_metrics_with_value_target_fail_line_and_status", async () => {
    await renderPage();
    const agreement = await card("Trainer agreement");
    expect(agreement).toHaveTextContent("67%");
    expect(agreement).toHaveTextContent("Target: 80% or more");
    expect(agreement).toHaveTextContent("Fails below 60%");
    expect(agreement).toHaveTextContent("Below target");
    expect(await card("Helpful ratings (4–5)")).toHaveTextContent("On target");
    expect(await card("Cue tried")).toHaveTextContent("Failing");
    expect(await card("7-day return")).toHaveTextContent("No data");
  });

  it("us23_each_metric_says_how_many_data_points_it_is_based_on", async () => {
    await renderPage();
    expect(await card("Trainer agreement")).toHaveTextContent("Based on 3 graded sets (2 agreed)");
    expect(await card("Helpful ratings (4–5)")).toHaveTextContent("Based on 4 ratings");
    expect(await card("Cue tried")).toHaveTextContent("Based on 4 answers");
  });

  it("us23_metric_without_data_shows_a_dash_not_zero_percent", async () => {
    await renderPage();
    const ret = await card("7-day return");
    expect(ret).toHaveTextContent("—");
    expect(within(ret).queryByText("0%")).not.toBeInTheDocument();   // exact: "50%" in the target line is fine
    expect(ret).toHaveTextContent("No data yet");
  });

  it("us23_lifters_still_in_their_first_week_are_mentioned", async () => {
    await renderPage();
    expect(await card("7-day return")).toHaveTextContent("1 lifter is still within their first 7 days");
  });

  it("us23_status_is_marked_for_screen_readers_and_by_color", async () => {
    await renderPage();
    const status = within(await card("Cue tried")).getByText("Failing");
    expect(status.className).toMatch(/red/);
    expect(within(await card("Helpful ratings (4–5)")).getByText("On target").className).toMatch(/green/);
  });

  it("us23_loads_the_default_range_and_shows_its_dates", async () => {
    await renderPage();
    expect(api.adminMetrics).toHaveBeenCalledWith(null, null, null);
    expect(await screen.findByLabelText("From")).toHaveValue("2026-10-14");
    expect(screen.getByLabelText("To")).toHaveValue("2026-11-12");
  });

  it("us23_filtering_by_date_range_reloads_the_metrics", async () => {
    await renderPage();
    const from = await screen.findByLabelText("From");
    await userEvent.clear(from);
    await userEvent.type(from, "2026-10-01");
    const to = screen.getByLabelText("To");
    await userEvent.clear(to);
    await userEvent.type(to, "2026-10-31");
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(api.adminMetrics).toHaveBeenLastCalledWith("2026-10-01", "2026-10-31", null);
  });

  it("us23_a_rejected_range_shows_the_reason", async () => {
    await renderPage();
    vi.mocked(api.adminMetrics).mockRejectedValue(new ApiError(422, "The start date must be on or before the end date"));
    await userEvent.click(await screen.findByRole("button", { name: "Show" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("on or before the end date");
  });

  it("us23_non_admins_see_admins_only", async () => {
    vi.mocked(api.adminMetrics).mockRejectedValue(new ApiError(403, "Admins only"));
    await renderPage();
    expect(await screen.findByRole("heading", { name: "403: Admins only" })).toBeInTheDocument();
  });

  it("us23_admin_analyses_page_links_to_the_metrics", async () => {
    vi.mocked(api.adminAnalyses).mockResolvedValue({ items: [] });
    vi.mocked(api.adminErrors).mockResolvedValue({ counts: {} });
    vi.mocked(api.adminCosts).mockReturnValue(new Promise(() => {}));
    await renderPage("@/app/admin/page");
    expect(await screen.findByRole("link", { name: "Hypothesis metrics" })).toHaveAttribute("href", "/admin/metrics");
  });
});
