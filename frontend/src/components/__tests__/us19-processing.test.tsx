import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ResultsPage from "@/app/results/[id]/page";
import { ResultsView } from "@/components/ResultsView";
import { UploadForm, type UploadArgs } from "@/components/UploadForm";
import { ApiError, api } from "@/lib/api";
import { passedResult, videoFile } from "@/test/fixtures";

const navigation = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), id: "a1" }));
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: navigation.id }),
  useRouter: () => navigation,
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, analysis: vi.fn(), retryAnalysis: vi.fn() } };
});

const noop = async () => {};
const steps = ["Uploading", "Measuring", "Writing feedback", "Checking"];

beforeEach(() => { vi.clearAllMocks(); navigation.id = "a1"; });
afterEach(() => { vi.useRealTimers(); });

describe("US-19 live processing status", () => {
  it("us19_uploading_shows_all_steps_in_order_and_preserves_byte_progress", async () => {
    let report: UploadArgs["onProgress"] = () => {};
    const upload = vi.fn((args: UploadArgs) => {
      report = args.onProgress;
      return new Promise<{ analysis_id: string }>(() => {});
    });
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    const list = screen.getByRole("list", { name: "Analysis progress" });
    expect(within(list).getAllByRole("listitem").map((item) => item.textContent)).toEqual(steps);
    expect(within(list).getByText("Uploading")).toHaveAttribute("aria-current", "step");
    act(() => report(42));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");
  });

  it.each(["measuring", "writing_feedback", "checking"] as const)("us19_highlights_the_actual_%s_step", (processing_stage) => {
    render(<ResultsView result={passedResult({ status: "processing", processing_stage })} onFeedback={noop} />);
    const list = screen.getByRole("list", { name: "Analysis progress" });
    expect(within(list).getAllByRole("listitem").map((item) => item.textContent)).toEqual(steps);
    const label = { measuring: "Measuring", writing_feedback: "Writing feedback", checking: "Checking" }[processing_stage];
    expect(within(list).getByText(label)).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("status")).toHaveTextContent(label);
    expect(screen.queryByRole("heading", { name: "Top fix" })).not.toBeInTheDocument();
  });

  it("us19_polls_without_refresh_then_opens_results_and_stops_polling", async () => {
    vi.useFakeTimers();
    vi.mocked(api.analysis)
      .mockResolvedValueOnce(passedResult({ status: "queued", processing_stage: null }))
      .mockResolvedValueOnce(passedResult({ status: "processing", processing_stage: "measuring" }))
      .mockResolvedValueOnce(passedResult({ status: "processing", processing_stage: "writing_feedback" }))
      .mockResolvedValueOnce(passedResult({ status: "processing", processing_stage: "checking" }))
      .mockResolvedValue(passedResult());
    render(<ResultsPage />);
    await act(async () => {});
    for (const label of ["Measuring", "Writing feedback", "Checking"]) {
      await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
      expect(screen.getByRole("status")).toHaveTextContent(label);
    }
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.getByRole("heading", { name: "Top fix" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(api.analysis).toHaveBeenCalledTimes(5);
  });

  it("us19_failed_analysis_has_retry_and_no_endless_status_indicator", async () => {
    vi.mocked(api.analysis).mockResolvedValue(passedResult({ status: "failed", error: "Analysis failed" }));
    vi.mocked(api.retryAnalysis).mockResolvedValue({ analysis_id: "a2", status: "queued" });
    render(<ResultsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong analyzing this video");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(api.retryAnalysis).toHaveBeenCalledWith("a1", null);
    expect(navigation.replace).toHaveBeenCalledWith("/results/a2");
  });

  it("us19_a_failed_retry_keeps_an_actionable_error", async () => {
    vi.mocked(api.analysis).mockResolvedValue(passedResult({ status: "failed" }));
    vi.mocked(api.retryAnalysis).mockRejectedValue(new ApiError(503, "Unavailable"));
    render(<ResultsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't restart this analysis");
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
  });

  it("us19_disables_retry_while_the_request_is_pending", async () => {
    vi.mocked(api.analysis).mockResolvedValue(passedResult({ status: "failed" }));
    vi.mocked(api.retryAnalysis).mockReturnValue(new Promise(() => {}));
    render(<ResultsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(screen.getByRole("button", { name: "Retrying…" })).toBeDisabled();
    expect(api.retryAnalysis).toHaveBeenCalledTimes(1);
  });

  it("us19_polling_network_failure_offers_retry_and_resumes_polling", async () => {
    vi.mocked(api.analysis).mockRejectedValueOnce(new ApiError(0, "Network error")).mockResolvedValue(passedResult());
    render(<ResultsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load this result");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: "Top fix" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(api.retryAnalysis).not.toHaveBeenCalled();
  });

  it("us19_cancels_scheduled_polling_when_leaving_the_page", async () => {
    vi.useFakeTimers();
    vi.mocked(api.analysis).mockResolvedValue(passedResult({ status: "processing", processing_stage: "measuring" }));
    const { unmount } = render(<ResultsPage />);
    await act(async () => {});
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(api.analysis).toHaveBeenCalledTimes(1);
  });

  it("us19_a_stalled_status_request_times_out_to_an_actionable_error", async () => {
    vi.useFakeTimers();
    vi.mocked(api.analysis).mockImplementation((_id, _token, signal) => new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new ApiError(0, "Network error")), { once: true });
    }));
    render(<ResultsPage />);
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load this result");
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("us19_route_changes_discard_late_responses_from_the_previous_analysis", async () => {
    let finishOld: (result: ReturnType<typeof passedResult>) => void = () => {};
    vi.mocked(api.analysis).mockReturnValueOnce(new Promise((resolve) => { finishOld = resolve; }))
      .mockResolvedValue(passedResult({ analysis_id: "a2", top_fix: null, no_major_issues: true }));
    const { rerender } = render(<ResultsPage />);
    navigation.id = "a2";
    rerender(<ResultsPage />);
    expect(await screen.findByText("No major issues found")).toBeInTheDocument();
    await act(async () => { finishOld(passedResult()); });
    expect(screen.getByText("No major issues found")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Top fix" })).not.toBeInTheDocument();
  });
});
