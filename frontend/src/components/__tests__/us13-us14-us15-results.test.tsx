import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NotMeasured } from "@/components/NotMeasured";
import { ResultsView } from "@/components/ResultsView";
import { UploadForm } from "@/components/UploadForm";
import { passedResult, videoFile } from "@/test/fixtures";

const noop = async () => {};

describe("US-13 say what couldn't be measured", () => {
  it("us13_not_measured_checks_listed_with_reasons", () => {
    render(<NotMeasured items={[
      { check: "knee_cave", name: "Knees cave inward", reason: "needs a front view" },
      { check: "rounded_back", name: "Your back rounds during the pull", reason: "ears not clearly visible (pose confidence below 0.5)" },
    ]} />);
    const section = screen.getByRole("region", { name: "Not measured" });
    expect(section).toHaveTextContent("Knees cave inward");
    expect(section).toHaveTextContent("needs a front view");
    expect(section).toHaveTextContent("ears not clearly visible (pose confidence below 0.5)");
  });

  it("us13_section_hidden_when_everything_was_measured", () => {
    const { container } = render(<NotMeasured items={[]} />);
    expect(container).toBeEmptyDOMElement();
    render(<ResultsView result={passedResult({ not_measured: [] })} onFeedback={noop} />);
    expect(screen.queryByRole("region", { name: "Not measured" })).not.toBeInTheDocument();
  });

  it("us13_not_measured_check_is_not_shown_as_a_fault", () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    const fix = screen.getByRole("region", { name: "Top fix" });
    expect(fix).not.toHaveTextContent("Knees cave inward");
    expect(screen.getByRole("region", { name: "Not measured" })).toHaveTextContent("Knees cave inward");
  });
});

describe("US-14 safety issues come first", () => {
  it("us14_safety_top_fix_shows_a_warning_label", () => {
    render(<ResultsView result={passedResult({
      top_fix: { fault_id: "knee_cave", title: "Knees cave inward", category: "safety", safety: true, reps: [4] },
    })} onFeedback={noop} />);
    const fix = screen.getByRole("region", { name: "Top fix" });
    expect(within(fix).getByText("Safety issue")).toBeInTheDocument();
  });

  it("us14_technique_fix_has_no_warning_label", () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    expect(screen.queryByText("Safety issue")).not.toBeInTheDocument();
  });

  it("us14_safety_faults_under_see_more_are_labeled_too", async () => {
    render(<ResultsView result={passedResult({
      other_faults: [{ fault_id: "elbow_flare", title: "Elbows flare out too wide", category: "safety", safety: true, reps: [2] }],
    })} onFeedback={noop} />);
    await userEvent.click(screen.getByRole("button", { name: "See more" }));
    expect(screen.getByText("Safety issue")).toBeInTheDocument();
  });
});

describe("US-15 recommend a professional if I mention pain", () => {
  it("us15_note_field_is_optional_and_limited_to_300_characters", async () => {
    const upload = vi.fn().mockResolvedValue({ analysis_id: "a1" });
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    const note = screen.getByLabelText("Anything we should know? (optional)");
    expect(note).toHaveAttribute("maxLength", "300");
    expect(note).not.toBeRequired();
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(upload).toHaveBeenCalledWith(expect.objectContaining({ note: "" }));
  });

  it("us15_note_counter_and_text_are_sent", async () => {
    const upload = vi.fn().mockResolvedValue({ analysis_id: "a1" });
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    await userEvent.type(screen.getByLabelText("Anything we should know? (optional)"), "my knee hurts");
    expect(screen.getByText("13/300")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(upload).toHaveBeenCalledWith(expect.objectContaining({ note: "my knee hurts" }));
  });

  it("us15_note_cannot_exceed_300_characters", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    const note = screen.getByLabelText("Anything we should know? (optional)") as HTMLTextAreaElement;
    await userEvent.click(note);
    await userEvent.paste("a".repeat(320));
    expect(note.value).toHaveLength(300);
  });

  it("us15_results_show_the_professional_recommendation", () => {
    const message = "You mentioned pain or an injury. Please see a doctor or physical therapist before you keep training this lift.";
    render(<ResultsView result={passedResult({ professional_message: message })} onFeedback={noop} />);
    expect(screen.getByRole("note", { name: "See a professional" })).toHaveTextContent(message);
  });

  it("us15_no_recommendation_without_pain", () => {
    render(<ResultsView result={passedResult()} onFeedback={noop} />);
    expect(screen.queryByRole("note", { name: "See a professional" })).not.toBeInTheDocument();
  });
});
