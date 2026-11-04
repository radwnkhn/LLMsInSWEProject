import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AdminAnalysesTable } from "@/components/AdminAnalysesTable";
import { ErrorSummary } from "@/components/ErrorSummary";
import { HistoryList } from "@/components/HistoryList";
import { AdminForbidden } from "@/components/AdminForbidden";
import type { AdminRow, HistoryItem } from "@/lib/types";

const history: HistoryItem[] = [
  { analysis_id: "h3", created_at: "2026-11-03T10:00:00Z", lift: "deadlift", lift_label: "Deadlift", rep_count: 3,
    top_fix_title: "Hips shoot up before the bar leaves the floor", status: "done", final_status: "passed_first_try", status_label: "Analyzed" },
  { analysis_id: "h2", created_at: "2026-11-02T10:00:00Z", lift: "squat", lift_label: "Squat", rep_count: 5,
    top_fix_title: null, status: "done", final_status: "fallback", status_label: "Measurements only" },
  { analysis_id: "h1", created_at: "2026-11-01T10:00:00Z", lift: "squat", lift_label: "Squat", rep_count: 0,
    top_fix_title: null, status: "done", final_status: "unanalyzable", status_label: "Couldn't analyze" },
];

const admin: AdminRow[] = [
  { analysis_id: "x3", created_at: "2026-11-03T10:00:00Z", user_email: "a@virginia.edu", lift: "squat", lift_label: "Squat",
    attempt_count: 0, final_status: "unanalyzable", final_status_label: "Couldn't analyze" },
  { analysis_id: "x2", created_at: "2026-11-02T10:00:00Z", user_email: "b@virginia.edu", lift: "deadlift", lift_label: "Deadlift",
    attempt_count: 3, final_status: "fallback", final_status_label: "Fallback" },
  { analysis_id: "x1", created_at: "2026-11-01T10:00:00Z", user_email: "a@virginia.edu", lift: "squat", lift_label: "Squat",
    attempt_count: 2, final_status: "passed_after_retry", final_status_label: "Passed after retry" },
];

describe("US-17 upload history", () => {
  it("us17_lists_entries_with_date_lift_reps_and_top_fix", () => {
    render(<HistoryList items={history} />);
    const first = screen.getAllByRole("listitem")[0];
    expect(first).toHaveTextContent("Deadlift");
    expect(first).toHaveTextContent("3 reps");
    expect(first).toHaveTextContent("Hips shoot up before the bar leaves the floor");
    expect(first).toHaveTextContent("Nov 3, 2026");
    expect(within(first).getByRole("link")).toHaveAttribute("href", "/results/h3");
  });

  it("us17_history_can_be_filtered_by_lift", async () => {
    render(<HistoryList items={history} />);
    await userEvent.selectOptions(screen.getByLabelText("Lift"), "squat");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    await userEvent.selectOptions(screen.getByLabelText("Lift"), "bench_press");
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(screen.getByText("No uploads yet for this lift.")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Lift"), "all");
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("us17_unanalyzable_and_fallback_entries_show_their_status", () => {
    render(<HistoryList items={history} />);
    const [, fallback, unanalyzable] = screen.getAllByRole("listitem");
    expect(fallback).toHaveTextContent("Measurements only");
    expect(unanalyzable).toHaveTextContent("Couldn't analyze");
  });
});

describe("US-18 inspect analyses and validator logs", () => {
  it("us18_table_shows_lift_attempts_and_final_status", () => {
    render(<AdminAnalysesTable items={admin} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("Deadlift");
    expect(rows[1]).toHaveTextContent("3");
    expect(rows[1]).toHaveTextContent("Fallback");
    expect(within(rows[1]).getByRole("link")).toHaveAttribute("href", "/admin/analyses/x2");
  });

  it("us18_filter_by_lift_and_final_status", async () => {
    render(<AdminAnalysesTable items={admin} />);
    await userEvent.selectOptions(screen.getByLabelText("Lift"), "squat");
    expect(screen.getAllByRole("row").slice(1)).toHaveLength(2);
    await userEvent.selectOptions(screen.getByLabelText("Final status"), "passed_after_retry");
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("Passed after retry");
  });

  it("us18_status_filter_offers_the_four_final_statuses", () => {
    render(<AdminAnalysesTable items={admin} />);
    const options = within(screen.getByLabelText("Final status")).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["All", "Passed first try", "Passed after retry", "Fallback", "Couldn't analyze"]);
  });

  it("us18_error_summary_shows_counts_per_error_type", () => {
    render(<ErrorSummary counts={{ rep_count: 4, fault_not_confirmed: 2 }} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Wrong rep count");
    expect(rows[0]).toHaveTextContent("4");
    expect(rows[1]).toHaveTextContent("Fault not confirmed by measurements");
    expect(rows[1]).toHaveTextContent("2");
  });

  it("us18_error_summary_empty_state", () => {
    render(<ErrorSummary counts={{}} />);
    expect(screen.getByText("No validator errors yet.")).toBeInTheDocument();
  });

  it("us18_non_admins_see_403", () => {
    render(<AdminForbidden />);
    expect(screen.getByRole("heading", { name: "403: Admins only" })).toBeInTheDocument();
  });
});
