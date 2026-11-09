import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ComparisonView } from "@/components/ComparisonView";
import { HistoryList } from "@/components/HistoryList";
import { isProtectedPath } from "@/lib/session";
import type { AnalysisComparison, HistoryItem } from "@/lib/types";
import { passedResult } from "@/test/fixtures";

const items: HistoryItem[] = [
  { analysis_id: "new", created_at: "2026-11-09T12:00:00Z", lift: "squat", lift_label: "Squat", rep_count: 5,
    top_fix_title: null, status: "done", final_status: "passed_first_try", status_label: "Analyzed" },
  { analysis_id: "old", created_at: "2026-11-08T12:00:00Z", lift: "squat", lift_label: "Squat", rep_count: 3,
    top_fix_title: "Hips rise before your shoulders", status: "done", final_status: "passed_first_try", status_label: "Analyzed" },
  { analysis_id: "deadlift", created_at: "2026-11-07T12:00:00Z", lift: "deadlift", lift_label: "Deadlift", rep_count: 3,
    top_fix_title: null, status: "done", final_status: "passed_first_try", status_label: "Analyzed" },
];

export function comparison(status: AnalysisComparison["fault_comparison"]["status"] = "not_detected"): AnalysisComparison {
  return {
    older: passedResult({ analysis_id: "old", created_at: items[1].created_at, rep_count: 3 }),
    newer: passedResult({ analysis_id: "new", top_fix: null }),
    metrics: [
      { metric: "torso_lean_increase_deg", label: "Torso lean increase", unit: "°", aggregation: "Maximum", older: 14.2, newer: 0 },
      { metric: "bar_drift_ratio", label: "Bar drift", unit: "thigh lengths", aggregation: "Maximum", older: 0.2, newer: null },
    ],
    fault_comparison: { fault_id: "hips_rise_early", title: "Hips rise before your shoulders", status, older_reps: [2, 3], newer_reps: status === "still_present" ? [4, 5] : [] },
  };
}

describe("US-20 compare uploads", () => {
  it("us20_history_selects_two_same_lift_uploads_and_opens_the_comparison", async () => {
    render(<HistoryList items={items} />);
    const choices = screen.getAllByRole("checkbox");
    expect(screen.getByRole("button", { name: "Compare selected uploads" })).toBeDisabled();
    await userEvent.click(choices[0]);
    await userEvent.click(choices[1]);
    expect(screen.getByRole("link", { name: "Compare selected uploads" })).toHaveAttribute("href", "/compare?first=new&second=old");
  });

  it("us20_a_different_lift_is_disabled_after_the_first_selection", async () => {
    render(<HistoryList items={items} />);
    const choices = screen.getAllByRole("checkbox");
    await userEvent.click(choices[0]);
    expect(choices[2]).toBeDisabled();
    expect(choices[1]).toBeEnabled();
    await userEvent.click(choices[0]);
    expect(choices[2]).toBeEnabled();
  });

  it("us20_only_two_completed_measurable_uploads_can_be_selected", async () => {
    render(<HistoryList items={[...items, { ...items[0], analysis_id: "failed", status: "failed" },
      { ...items[0], analysis_id: "unmeasurable", final_status: "unanalyzable" },
      { ...items[0], analysis_id: "pending", status: "processing" }]} />);
    const choices = screen.getAllByRole("checkbox");
    for (const index of [3, 4, 5]) expect(choices[index]).toBeDisabled();
    await userEvent.click(choices[0]);
    await userEvent.click(choices[1]);
    expect(choices[2]).toBeDisabled();
  });

  it("us20_changing_the_history_filter_clears_hidden_selections", async () => {
    render(<HistoryList items={items} />);
    await userEvent.click(screen.getAllByRole("checkbox")[0]);
    await userEvent.selectOptions(screen.getByLabelText("Lift"), "deadlift");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByRole("checkbox")).toBeEnabled();
  });

  it("us20_two_videos_and_their_measurements_are_shown_side_by_side", () => {
    render(<ComparisonView comparison={comparison()} />);
    const earlier = screen.getByRole("region", { name: "Earlier upload" });
    const newer = screen.getByRole("region", { name: "Newer upload" });
    expect(within(earlier).getByText("3 reps")).toBeInTheDocument();
    expect(within(newer).getByText("5 reps")).toBeInTheDocument();
    expect(screen.getByLabelText("Earlier video")).toHaveAttribute("src", comparison().older.video_url);
    expect(screen.getByLabelText("Newer video")).toHaveAttribute("src", comparison().newer.video_url);
    const table = screen.getByRole("table", { name: "Key measurements" });
    expect(within(table).getByText("14.2°")).toBeInTheDocument();
    expect(within(table).getByText("0°")).toBeInTheDocument();
    expect(within(table).getByText("Not measured")).toBeInTheDocument();
  });

  it.each([
    ["not_detected", "Not detected in the newer upload"],
    ["still_present", "Still present in the newer upload"],
    ["not_measured", "Not measurable in the newer upload"],
    ["no_previous_fault", "No top fault was reported in the earlier upload"],
    ["unavailable", "The earlier upload has measurements only"],
  ] as const)("us20_displays_the_%s_outcome_without_claiming_a_cure", (status, message) => {
    render(<ComparisonView comparison={comparison(status)} />);
    expect(screen.getByRole("region", { name: "Earlier top fix" })).toHaveTextContent(message);
    if (status === "still_present") expect(screen.getByText("Reps 4, 5")).toBeInTheDocument();
  });

  it("us20_changing_camera_angles_has_context_for_interpreting_measurements", () => {
    const data = comparison();
    data.newer.camera_angle = "front";
    render(<ComparisonView comparison={data} />);
    expect(screen.getByRole("note")).toHaveTextContent("different camera angles");
  });

  it("us20_comparison_page_requires_a_session", () => {
    expect(isProtectedPath("/compare")).toBe(true);
  });
});
