import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultsView } from "@/components/ResultsView";
import { fallbackResult, passedResult, unanalyzableResult } from "@/test/fixtures";

const noop = async () => {};

describe("US-05 tell me when a video can't be analyzed", () => {
  it("us05_unanalyzable_result_shows_the_reason_and_a_refilm_link", () => {
    render(<ResultsView result={unanalyzableResult("Couldn't analyze: body not clearly visible")} onFeedback={noop} />);
    expect(screen.getByRole("heading", { name: "Couldn't analyze: body not clearly visible" })).toBeInTheDocument();
    const refilm = screen.getByRole("link", { name: "Refilm" });
    expect(refilm).toHaveAttribute("href", "/upload?lift=squat&guide=1");
    expect(screen.queryByText(/top fix/i)).not.toBeInTheDocument();
  });
});

describe("US-09 safe fallback", () => {
  it("us09_fallback_shows_the_note_and_measurements_but_no_coaching", () => {
    render(<ResultsView result={fallbackResult()} onFeedback={noop} />);
    expect(screen.getByText("Coaching feedback isn't available for this video. Here are your measurements.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /top fix/i })).not.toBeInTheDocument();
    expect(screen.queryByText("No major issues found")).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem", { name: /^Rep \d/ })).toHaveLength(5);
  });

  it("us09_no_fallback_note_on_a_normal_result", () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    expect(screen.queryByText(/Coaching feedback isn't available/)).not.toBeInTheDocument();
  });

  it("us09_processing_and_failed_states", () => {
    const { rerender } = render(<ResultsView result={passedResult({ status: "processing" })} onFeedback={noop} />);
    expect(screen.getByRole("status")).toHaveTextContent("Analyzing your set");
    rerender(<ResultsView result={passedResult({ status: "failed", error: "boom" })} onFeedback={noop} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong analyzing this video");
  });
});
