import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ResultsView } from "@/components/ResultsView";
import { passedResult } from "@/test/fixtures";

const noop = async () => {};

describe("US-10 show one top fix and one cue", () => {
  it("us10_shows_exactly_one_top_fix_in_plain_language", () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    expect(screen.getAllByRole("heading", { name: "Top fix" })).toHaveLength(1);
    const fix = screen.getByRole("region", { name: "Top fix" });
    expect(fix).toHaveTextContent("Hips rise before your shoulders");
    expect(fix).not.toHaveTextContent("hips_rise_early");
  });

  it("us10_shows_exactly_one_cue_with_the_top_fix", () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    const cues = screen.getAllByLabelText("Cue for your next set");
    expect(cues).toHaveLength(1);
    expect(cues[0]).toHaveTextContent("Drive your chest up with your hips");
    expect(cues[0].textContent!.trim().split(/\s+/).length).toBeLessThanOrEqual(12);
  });

  it("us10_other_faults_are_collapsed_under_see_more", async () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    const toggle = screen.getByRole("button", { name: "See more" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Bar drifts forward and back")).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Bar drifts forward and back")).toBeVisible();
  });

  it("us10_no_see_more_without_other_faults", () => {
    render(<ResultsView result={passedResult({ other_faults: [] })} onFeedback={noop} />);
    expect(screen.queryByRole("button", { name: "See more" })).not.toBeInTheDocument();
  });

  it("us10_no_major_issues_found", () => {
    render(<ResultsView result={passedResult({ top_fix: null, cue: null, other_faults: [], no_major_issues: true, annotated_frame: null })} onFeedback={noop} />);
    expect(screen.getByText("No major issues found")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Top fix" })).not.toBeInTheDocument();
  });

  // Found in manual testing: with most checks skipped for the camera angle, "No major issues found" read as
  // "your form is good". The message must say what wasn't checked.
  it("us10_no_major_issues_says_how_many_checks_were_skipped", () => {
    const skipped = [
      { check: "knee_cave", name: "Knees cave inward", reason: "needs a front view" },
      { check: "hips_rise_early", name: "Hips rise before your shoulders", reason: "needs a side view" },
    ];
    render(<ResultsView result={passedResult({ top_fix: null, cue: null, other_faults: [], no_major_issues: true,
      annotated_frame: null, not_measured: skipped })} onFeedback={noop} />);
    expect(screen.getByText("No major issues found")).toBeInTheDocument();
    expect(screen.getByText("2 checks couldn't be run from this video, so they aren't covered. See \"Not measured\" below."))
      .toBeInTheDocument();
  });

  it("us10_no_major_issues_says_one_check_was_skipped", () => {
    render(<ResultsView result={passedResult({ top_fix: null, cue: null, other_faults: [], no_major_issues: true,
      annotated_frame: null })} onFeedback={noop} />);
    expect(screen.getByText("1 check couldn't be run from this video, so it isn't covered. See \"Not measured\" below."))
      .toBeInTheDocument();
  });

  it("us10_no_major_issues_has_no_skipped_note_when_everything_was_checked", () => {
    render(<ResultsView result={passedResult({ top_fix: null, cue: null, other_faults: [], no_major_issues: true,
      annotated_frame: null, not_measured: [] })} onFeedback={noop} />);
    expect(screen.queryByText(/couldn't be run/)).not.toBeInTheDocument();
  });
});
