import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ComparePage from "@/app/compare/page";
import { ApiError, api } from "@/lib/api";
import type { AnalysisComparison } from "@/lib/types";
import { passedResult } from "@/test/fixtures";

const navigation = vi.hoisted(() => ({ query: "first=a1&second=a2", push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(navigation.query),
  useRouter: () => navigation,
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, comparison: vi.fn() } };
});

const data: AnalysisComparison = {
  older: passedResult(), newer: passedResult({ analysis_id: "a2" }), metrics: [],
  fault_comparison: { fault_id: "hips_rise_early", title: "Hips rise before your shoulders", status: "not_detected", older_reps: [4, 5], newer_reps: [] },
};

beforeEach(() => { vi.resetAllMocks(); navigation.query = "first=a1&second=a2"; });

describe("US-20 comparison page", () => {
  it("us20_fetches_the_selected_uploads_and_displays_the_comparison", async () => {
    vi.mocked(api.comparison).mockResolvedValue(data);
    render(<ComparePage />);
    expect(await screen.findByRole("heading", { name: "Compare Squat uploads" })).toBeInTheDocument();
    expect(api.comparison).toHaveBeenCalledWith("a1", "a2", null, expect.any(AbortSignal));
  });

  it("us20_missing_selection_sends_the_user_back_to_history_without_a_request", () => {
    navigation.query = "first=a1";
    render(<ComparePage />);
    expect(screen.getByRole("alert")).toHaveTextContent("Choose two uploads from your history");
    expect(screen.getByRole("link", { name: "Back to history" })).toHaveAttribute("href", "/history");
    expect(api.comparison).not.toHaveBeenCalled();
  });

  it.each([404, 409, 422])("us20_server_%s_errors_are_shown_without_private_results", async (status) => {
    vi.mocked(api.comparison).mockRejectedValue(new ApiError(status, "Choose two uploads of the same lift"));
    render(<ComparePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose two uploads of the same lift");
    expect(screen.queryByLabelText("Earlier video")).not.toBeInTheDocument();
  });

  it("us20_network_failure_can_be_retried", async () => {
    vi.mocked(api.comparison).mockRejectedValueOnce(new ApiError(0, "Network error")).mockResolvedValue(data);
    render(<ComparePage />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: "Compare Squat uploads" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("us20_an_expired_session_returns_to_login", async () => {
    vi.mocked(api.comparison).mockRejectedValue(new ApiError(401, "Please log in"));
    render(<ComparePage />);
    await act(async () => {});
    expect(navigation.push).toHaveBeenCalledWith(expect.stringContaining("/login?next="));
  });

  it("us20_leaving_the_comparison_aborts_the_pending_request", async () => {
    vi.mocked(api.comparison).mockReturnValue(new Promise(() => {}));
    const { unmount } = render(<ComparePage />);
    expect(api.comparison).toHaveBeenCalledTimes(1);
    const signal = vi.mocked(api.comparison).mock.calls[0][3];
    unmount();
    expect(signal?.aborted).toBe(true);
  });
});
