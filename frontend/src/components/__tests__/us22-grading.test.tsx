import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";
import { isProtectedPath } from "@/lib/session";
import type { AdminGradingAssignment, TrainerAssignment, TrainerAssignmentItem } from "@/lib/types";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "g1" }) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, adminTrainers: vi.fn(), assignGrading: vi.fn(), gradingAssignments: vi.fn(),
    trainerAssignments: vi.fn(), trainerAssignment: vi.fn(), answerAssignment: vi.fn(), gradeAssignment: vi.fn(),
    adminAnalyses: vi.fn(), adminErrors: vi.fn(), adminCosts: vi.fn() } };
});

// Pages are loaded at run time so each test reports its own failure while they don't exist yet.
async function renderPage(path: string) {
  const { default: Page } = (await import(/* @vite-ignore */ path)) as { default: ComponentType };
  render(<Page />);
}
const ADMIN_PAGE = "@/app/admin/grading/page";
const LIST_PAGE = "@/app/grading/page";
const GRADE_PAGE = "@/app/grading/[id]/page";

const HIPS = { fault_id: "hips_rise_early", name: "Hips rise before your shoulders" };
const LEAN = { fault_id: "excessive_forward_lean", name: "Chest drops too far forward" };
const NONE = { fault_id: null, name: "No major issue" };

const row = (overrides: Partial<AdminGradingAssignment> = {}): AdminGradingAssignment => ({
  assignment_id: "g1", analysis_id: "a1", lift: "squat", lift_label: "Squat", trainer_email: "trainer@virginia.edu",
  assigned_at: "2026-11-12T10:00:00+00:00", graded_at: null, status: "waiting", status_label: "To grade",
  trainer_answer: null, our_fault: HIPS, verdict: null, verdict_label: null, ...overrides,
});

const waiting = (overrides: Partial<TrainerAssignment> = {}): TrainerAssignment => ({
  assignment_id: "g1", lift: "squat", lift_label: "Squat", status: "waiting", status_label: "To grade",
  video_url: "http://api.test/v.mp4", fault_options: [HIPS, LEAN, NONE], trainer_answer: null, our_feedback: null,
  verdict: null, verdict_label: null, ...overrides,
});

const OURS = {
  top_fix: { fault_id: "hips_rise_early", title: "Hips rise before your shoulders", reps: [4, 5] },
  cue: "Drive your chest up with your hips", explanation: "Your torso tipped forward as you stood up.",
  other_faults: [{ fault_id: "bar_path_drift", title: "Bar drifts forward and back", reps: [4, 5] }],
  no_major_issues: false,
};
const answered = (overrides: Partial<TrainerAssignment> = {}) =>
  waiting({ status: "answered", status_label: "Answered", trainer_answer: LEAN, our_feedback: OURS, ...overrides });

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.adminTrainers).mockResolvedValue({ items: [{ id: "t1", email: "trainer@virginia.edu" },
    { id: "t2", email: "second.trainer@virginia.edu" }] });
  vi.mocked(api.gradingAssignments).mockResolvedValue({ items: [] });
});

describe("US-22 admin grading page", () => {
  it("us22_admin_assigns_a_sample_to_a_trainer_with_a_count_and_optional_lift", async () => {
    vi.mocked(api.assignGrading).mockResolvedValue({ requested: 5, assigned: 3, items: [row()] });
    await renderPage(ADMIN_PAGE);
    const form = await screen.findByRole("region", { name: "Assign a sample" });
    await userEvent.selectOptions(within(form).getByLabelText("Trainer"), "t2");
    const count = within(form).getByLabelText("Number of analyses");
    await userEvent.clear(count);
    await userEvent.type(count, "5");
    await userEvent.selectOptions(within(form).getByLabelText("Lift"), "deadlift");
    await userEvent.click(within(form).getByRole("button", { name: "Assign" }));
    expect(api.assignGrading).toHaveBeenCalledWith("t2", 5, "deadlift", null);
    expect(await within(form).findByRole("status")).toHaveTextContent("Assigned 3 of 5 requested analyses");
    expect(api.gradingAssignments).toHaveBeenCalledTimes(2);
  });

  it("us22_all_lifts_sends_no_lift", async () => {
    vi.mocked(api.assignGrading).mockResolvedValue({ requested: 1, assigned: 1, items: [row()] });
    await renderPage(ADMIN_PAGE);
    const form = await screen.findByRole("region", { name: "Assign a sample" });
    expect(within(form).getByLabelText("Lift")).toHaveValue("");
    await userEvent.click(within(form).getByRole("button", { name: "Assign" }));
    expect(api.assignGrading).toHaveBeenCalledWith("t1", 10, null, null);
  });

  it.each([["0"], ["51"], [""]])("us22_count_%s_is_rejected_before_assigning", async (value) => {
    await renderPage(ADMIN_PAGE);
    const form = await screen.findByRole("region", { name: "Assign a sample" });
    await userEvent.clear(within(form).getByLabelText("Number of analyses"));
    if (value) await userEvent.type(within(form).getByLabelText("Number of analyses"), value);
    await userEvent.click(within(form).getByRole("button", { name: "Assign" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("Choose a number from 1 to 50");
    expect(api.assignGrading).not.toHaveBeenCalled();
  });

  it("us22_nothing_left_to_assign_is_explained", async () => {
    vi.mocked(api.assignGrading).mockRejectedValue(new ApiError(409, "No analyses are left to assign to this trainer"));
    await renderPage(ADMIN_PAGE);
    const form = await screen.findByRole("region", { name: "Assign a sample" });
    await userEvent.click(within(form).getByRole("button", { name: "Assign" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("No analyses are left to assign");
  });

  it("us22_without_trainer_accounts_the_page_says_how_to_add_one", async () => {
    vi.mocked(api.adminTrainers).mockResolvedValue({ items: [] });
    await renderPage(ADMIN_PAGE);
    expect(await screen.findByText(/No trainer accounts yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign" })).not.toBeInTheDocument();
  });

  it("us22_admin_list_shows_trainer_status_both_faults_and_grade", async () => {
    vi.mocked(api.gradingAssignments).mockResolvedValue({ items: [
      row({ status: "graded", status_label: "Graded", trainer_answer: LEAN, verdict: "partly_correct",
        verdict_label: "Partly correct", graded_at: "2026-11-12T11:00:00+00:00" }),
      row({ assignment_id: "g2", our_fault: NONE }),
    ] });
    await renderPage(ADMIN_PAGE);
    const table = await screen.findByRole("region", { name: "Assignments" });
    const [graded, open] = within(table).getAllByRole("row").slice(1);
    for (const text of ["Squat", "trainer@virginia.edu", "Graded", "Chest drops too far forward",
      "Hips rise before your shoulders", "Partly correct"]) expect(graded).toHaveTextContent(text);
    expect(open).toHaveTextContent("To grade");
    expect(open).toHaveTextContent("No major issue");
    expect(within(open).getByRole("link", { name: "View analysis" })).toHaveAttribute("href", "/admin/analyses/a1");
  });

  it("us22_non_admins_see_admins_only", async () => {
    vi.mocked(api.adminTrainers).mockRejectedValue(new ApiError(403, "Admins only"));
    vi.mocked(api.gradingAssignments).mockRejectedValue(new ApiError(403, "Admins only"));
    await renderPage(ADMIN_PAGE);
    expect(await screen.findByRole("heading", { name: "403: Admins only" })).toBeInTheDocument();
  });

  it("us22_admin_analyses_page_links_to_trainer_grading", async () => {
    vi.mocked(api.adminAnalyses).mockResolvedValue({ items: [] });
    vi.mocked(api.adminErrors).mockResolvedValue({ counts: {} });
    vi.mocked(api.adminCosts).mockReturnValue(new Promise(() => {}));
    await renderPage("@/app/admin/page");
    expect(await screen.findByRole("link", { name: "Trainer grading" })).toHaveAttribute("href", "/admin/grading");
  });
});

describe("US-22 trainer pages", () => {
  const items: TrainerAssignmentItem[] = [
    { assignment_id: "g2", lift: "bench_press", lift_label: "Bench Press", assigned_at: "2026-11-12T10:00:00+00:00",
      status: "waiting", status_label: "To grade" },
    { assignment_id: "g1", lift: "squat", lift_label: "Squat", assigned_at: "2026-11-11T10:00:00+00:00",
      status: "graded", status_label: "Graded" },
  ];

  it("us22_trainer_list_links_each_assignment_with_lift_and_status", async () => {
    vi.mocked(api.trainerAssignments).mockResolvedValue({ items });
    await renderPage(LIST_PAGE);
    const links = await screen.findAllByRole("link", { name: /Bench Press|Squat/ });
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/grading/g2", "/grading/g1"]);
    expect(links[0]).toHaveTextContent("To grade");
    expect(links[1]).toHaveTextContent("Graded");
  });

  it("us22_trainer_list_says_when_there_is_nothing_to_grade", async () => {
    vi.mocked(api.trainerAssignments).mockResolvedValue({ items: [] });
    await renderPage(LIST_PAGE);
    expect(await screen.findByText("Nothing to grade right now.")).toBeInTheDocument();
  });

  it("us22_non_trainers_see_trainers_only", async () => {
    vi.mocked(api.trainerAssignments).mockRejectedValue(new ApiError(403, "Trainers only"));
    await renderPage(LIST_PAGE);
    expect(await screen.findByRole("heading", { name: "403: Trainers only" })).toBeInTheDocument();
  });

  it("us22_before_answering_the_trainer_sees_the_video_but_not_our_feedback", async () => {
    vi.mocked(api.trainerAssignment).mockResolvedValue(waiting());
    await renderPage(GRADE_PAGE);
    const own = await screen.findByRole("region", { name: "Your top fault" });
    expect(document.querySelector("video")).toHaveAttribute("src", "http://api.test/v.mp4");
    expect(within(own).getAllByRole("radio").map((r) => r.closest("label")?.textContent))
      .toEqual(["Hips rise before your shoulders", "Chest drops too far forward", "No major issue"]);
    expect(screen.queryByRole("region", { name: "Our feedback" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Your grade" })).not.toBeInTheDocument();
    expect(screen.queryByText("Drive your chest up with your hips")).not.toBeInTheDocument();
  });

  it("us22_answer_needs_a_choice_then_reveals_our_feedback", async () => {
    vi.mocked(api.trainerAssignment).mockResolvedValue(waiting());
    vi.mocked(api.answerAssignment).mockResolvedValue(answered());
    await renderPage(GRADE_PAGE);
    const own = await screen.findByRole("region", { name: "Your top fault" });
    await userEvent.click(within(own).getByRole("button", { name: "Save my answer" }));
    expect(await within(own).findByRole("alert")).toHaveTextContent("Choose a fault");
    expect(api.answerAssignment).not.toHaveBeenCalled();
    await userEvent.click(within(own).getByLabelText("Chest drops too far forward"));
    await userEvent.click(within(own).getByRole("button", { name: "Save my answer" }));
    expect(api.answerAssignment).toHaveBeenCalledWith("g1", "excessive_forward_lean", null);
    const ours = await screen.findByRole("region", { name: "Our feedback" });
    expect(ours).toHaveTextContent("Hips rise before your shoulders");
    expect(ours).toHaveTextContent("Drive your chest up with your hips");
    expect(ours).toHaveTextContent("Bar drifts forward and back");
    expect(screen.getByText("Your top fault: Chest drops too far forward")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save my answer" })).not.toBeInTheDocument();
  });

  it("us22_no_major_issue_is_sent_as_no_fault", async () => {
    vi.mocked(api.trainerAssignment).mockResolvedValue(waiting());
    vi.mocked(api.answerAssignment).mockResolvedValue(answered({ trainer_answer: NONE }));
    await renderPage(GRADE_PAGE);
    const own = await screen.findByRole("region", { name: "Your top fault" });
    await userEvent.click(within(own).getByLabelText("No major issue"));
    await userEvent.click(within(own).getByRole("button", { name: "Save my answer" }));
    expect(api.answerAssignment).toHaveBeenCalledWith("g1", null, null);
  });

  it("us22_trainer_marks_our_feedback_correct_partly_correct_or_wrong", async () => {
    vi.mocked(api.trainerAssignment).mockResolvedValue(answered());
    vi.mocked(api.gradeAssignment).mockResolvedValue(answered({ status: "graded", status_label: "Graded",
      verdict: "partly_correct", verdict_label: "Partly correct" }));
    await renderPage(GRADE_PAGE);
    const grade = await screen.findByRole("region", { name: "Your grade" });
    expect(within(grade).getAllByRole("radio").map((r) => r.closest("label")?.textContent))
      .toEqual(["Correct", "Partly correct", "Wrong"]);
    await userEvent.click(within(grade).getByLabelText("Partly correct"));
    await userEvent.click(within(grade).getByRole("button", { name: "Save grade" }));
    expect(api.gradeAssignment).toHaveBeenCalledWith("g1", "partly_correct", null);
    expect(await within(grade).findByRole("status")).toHaveTextContent("Saved: Partly correct");
  });

  it("us22_clean_feedback_is_shown_as_no_major_issues", async () => {
    vi.mocked(api.trainerAssignment).mockResolvedValue(answered({ our_feedback: { top_fix: null, cue: "",
      explanation: "Solid set.", other_faults: [], no_major_issues: true } }));
    await renderPage(GRADE_PAGE);
    expect(await screen.findByRole("region", { name: "Our feedback" })).toHaveTextContent("No major issues found");
  });

  it("us22_grade_page_never_shows_lifter_details", async () => {
    vi.mocked(api.trainerAssignment).mockResolvedValue(answered());
    await renderPage(GRADE_PAGE);
    await screen.findByRole("region", { name: "Our feedback" });
    expect(document.body.textContent).not.toMatch(/@|\.mp4/);
  });
});

describe("US-22 sign-in", () => {
  it("us22_grading_pages_need_a_signed_in_user", () => {
    expect(isProtectedPath("/grading")).toBe(true);
    expect(isProtectedPath("/grading/g1")).toBe(true);
  });
});
