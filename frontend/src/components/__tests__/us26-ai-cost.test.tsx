import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPage from "@/app/admin/page";
import AdminAnalysisPage from "@/app/admin/analyses/[id]/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "a1" }) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, adminAnalysis: vi.fn(), adminAnalyses: vi.fn(), adminErrors: vi.fn(),
    adminCosts: vi.fn() } };
});

const analysis = { analysis_id: "a1", created_at: "2026-11-10T12:00:00Z", user_email: "l@virginia.edu", lift: "squat" as const,
  lift_label: "Squat", attempt_count: 2, final_status: "passed_after_retry" as const, final_status_label: "Passed after retry" };

const attempt = (n: number, extra: object) => ({ attempt_number: n, output_text: "{}", input_tokens: 2000 + n,
  output_tokens: 300 + n, passed: n === 2, errors: [], provider: "claude", model: "claude-sonnet-5-5", cost: 0.007, ...extra });

function detail(overrides: object = {}) {
  return { analysis, video_url: null, measurements: [], result: null,
    attempts: [attempt(1, { cost: 0.007012 }), attempt(2, { cost: 0.007024 })],
    usage: { input_tokens: 4003, output_tokens: 603, cost: 0.014036, unknown_cost_attempts: 0 }, ...overrides };
}

const summary = { start: "2026-10-12", end: "2026-11-10", analysis_count: 3, attempt_count: 5, retry_attempt_count: 2,
  input_tokens: 3_000_000, output_tokens: 100_000, total_cost: 7, average_cost: 7 / 3, retry_cost: 4, retry_share: 4 / 7,
  unknown_cost_attempts: 1 };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.adminAnalyses).mockResolvedValue({ items: [] });
  vi.mocked(api.adminErrors).mockResolvedValue({ counts: {} });
});

describe("US-26 cost on the analysis detail page", () => {
  it("us26_each_attempt_shows_provider_model_tokens_and_cost", async () => {
    vi.mocked(api.adminAnalysis).mockResolvedValue(detail() as never);
    render(<AdminAnalysisPage />);
    const first = await screen.findByRole("article", { name: /Attempt 1/ });
    expect(first).toHaveTextContent("claude · claude-sonnet-5-5");
    expect(first).toHaveTextContent("2,001 in / 301 out tokens");
    expect(first).toHaveTextContent("$0.0070");
    expect(screen.getByRole("article", { name: /Attempt 2/ })).toHaveTextContent("$0.0070");
  });

  it("us26_the_analysis_total_shows_all_tokens_and_cost", async () => {
    vi.mocked(api.adminAnalysis).mockResolvedValue(detail() as never);
    render(<AdminAnalysisPage />);
    const total = await screen.findByRole("region", { name: "AI usage" });
    expect(total).toHaveTextContent("4,003 in / 603 out tokens");
    expect(total).toHaveTextContent("$0.0140");
  });

  it("us26_unknown_models_show_unknown_cost_instead_of_failing", async () => {
    vi.mocked(api.adminAnalysis).mockResolvedValue(detail({
      attempts: [attempt(1, { cost: null, provider: null, model: null }), attempt(2, { cost: null, model: "new-model" })],
      usage: { input_tokens: 4003, output_tokens: 603, cost: null, unknown_cost_attempts: 2 },
    }) as never);
    render(<AdminAnalysisPage />);
    const first = await screen.findByRole("article", { name: /Attempt 1/ });
    expect(first).toHaveTextContent("Unknown model");
    expect(first).toHaveTextContent("Unknown cost");
    expect(screen.getByRole("article", { name: /Attempt 2/ })).toHaveTextContent("claude · new-model");
    const total = screen.getByRole("region", { name: "AI usage" });
    expect(total).toHaveTextContent("Unknown cost");
    expect(total).toHaveTextContent("2 attempts have no price in the price table");
  });
});

describe("US-26 cost summary on the admin page", () => {
  it("us26_summary_shows_total_average_and_retry_share_for_the_range", async () => {
    vi.mocked(api.adminCosts).mockResolvedValue(summary);
    render(<AdminPage />);
    const region = await screen.findByRole("region", { name: "AI cost" });
    expect(await within(region).findByText("$7.00")).toBeInTheDocument();
    expect(region).toHaveTextContent("Analyses3");
    expect(region).toHaveTextContent("Average per analysis$2.33");
    expect(region).toHaveTextContent("Spent on correction retries57%");
    expect(region).toHaveTextContent("1 attempt has an unknown cost and isn't included");
    expect(api.adminCosts).toHaveBeenCalledWith(null, null, null);
    expect(within(region).getByLabelText("From")).toHaveValue("2026-10-12");
    expect(within(region).getByLabelText("To")).toHaveValue("2026-11-10");
  });

  it("us26_a_small_but_real_retry_share_is_not_shown_as_zero", async () => {
    vi.mocked(api.adminCosts).mockResolvedValue({ ...summary, retry_share: 0.004, unknown_cost_attempts: 0 });
    render(<AdminPage />);
    const region = await screen.findByRole("region", { name: "AI cost" });
    expect(await within(region).findByText("<1%")).toBeInTheDocument();
  });

  it("us26_choosing_dates_reloads_the_summary_for_that_range", async () => {
    vi.mocked(api.adminCosts).mockResolvedValueOnce(summary)
      .mockResolvedValueOnce({ ...summary, start: "2026-11-01", end: "2026-11-05", analysis_count: 0, attempt_count: 0,
        total_cost: 0, average_cost: null, retry_cost: 0, retry_share: null, unknown_cost_attempts: 0 });
    render(<AdminPage />);
    const region = await screen.findByRole("region", { name: "AI cost" });
    await within(region).findByText("$7.00");
    const from = within(region).getByLabelText("From");
    await userEvent.clear(from);
    await userEvent.type(from, "2026-11-01");
    const to = within(region).getByLabelText("To");
    await userEvent.clear(to);
    await userEvent.type(to, "2026-11-05");
    await userEvent.click(within(region).getByRole("button", { name: "Show" }));
    expect(api.adminCosts).toHaveBeenLastCalledWith("2026-11-01", "2026-11-05", null);
    expect(await within(region).findByText("No analyses with AI attempts in this range.")).toBeInTheDocument();
  });

  it("us26_a_bad_range_shows_the_reason", async () => {
    const { ApiError } = await import("@/lib/api");
    vi.mocked(api.adminCosts).mockResolvedValueOnce(summary)
      .mockRejectedValueOnce(new ApiError(422, "The start date must be on or before the end date"));
    render(<AdminPage />);
    const region = await screen.findByRole("region", { name: "AI cost" });
    await within(region).findByText("$7.00");
    await userEvent.click(within(region).getByRole("button", { name: "Show" }));
    expect(await within(region).findByRole("alert")).toHaveTextContent("start date must be on or before the end date");
  });
});
