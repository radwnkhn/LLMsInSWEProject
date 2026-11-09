import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FeedbackForm } from "@/components/FeedbackForm";
import { PreviousCuePrompt } from "@/components/PreviousCuePrompt";
import { ResultsView } from "@/components/ResultsView";
import { fallbackResult, passedResult, unanalyzableResult } from "@/test/fixtures";

describe("US-16 rate the feedback and say if I tried the cue", () => {
  it("us16_asks_for_a_1_to_5_rating_and_whether_the_cue_was_tried", () => {
    render(<FeedbackForm initial={null} onSubmit={vi.fn()} />);
    const rating = screen.getByRole("radiogroup", { name: "How helpful was this feedback?" });
    expect(within(rating).getAllByRole("radio").map((r) => r.getAttribute("value"))).toEqual(["1", "2", "3", "4", "5"]);
    const tried = screen.getByRole("radiogroup", { name: "Did you try the cue?" });
    expect(within(tried).getAllByRole("radio").map((r) => r.closest("label")!.textContent!.trim())).toEqual(["Yes", "No", "Not yet"]);
  });

  it("us16_submits_the_answers", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<FeedbackForm initial={null} onSubmit={onSubmit} />);
    await userEvent.click(screen.getByLabelText("4"));
    await userEvent.click(screen.getByLabelText("Not yet"));
    await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));
    expect(onSubmit).toHaveBeenCalledWith({ rating: 4, tried_cue: "not_yet" });
    expect(await screen.findByText("Thanks for the feedback!")).toBeInTheDocument();
  });

  it("us16_shows_the_previous_answer_and_allows_changing_it", () => {
    render(<FeedbackForm initial={{ rating: 2, tried_cue: "yes" }} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("2")).toBeChecked();
    expect(screen.getByLabelText("Yes")).toBeChecked();
    expect(screen.getByRole("button", { name: "Update feedback" })).toBeEnabled();
  });

  it("us16_send_disabled_until_something_is_chosen", () => {
    render(<FeedbackForm initial={null} onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Send feedback" })).toBeDisabled();
  });

  it("us16_every_results_screen_asks_for_feedback", () => {
    for (const result of [passedResult(), fallbackResult(), unanalyzableResult()]) {
      const { unmount } = render(<ResultsView result={result} onFeedback={vi.fn()} />);
      expect(screen.getByRole("radiogroup", { name: "How helpful was this feedback?" })).toBeInTheDocument();
      unmount();
    }
  });

  it("us16_cue_question_only_when_there_was_a_cue", () => {
    render(<ResultsView result={fallbackResult()} onFeedback={vi.fn()} />);
    expect(screen.queryByRole("radiogroup", { name: "Did you try the cue?" })).not.toBeInTheDocument();
  });

  it("us16_asks_about_the_previous_cue_for_the_same_lift", async () => {
    const onAnswer = vi.fn().mockResolvedValue(undefined);
    render(<PreviousCuePrompt prompt={{ analysis_id: "old", cue: "Push your knees out", lift: "squat" }} onAnswer={onAnswer} />);
    expect(screen.getByText(/Last squat, your cue was “Push your knees out”\. Did you try it\?/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onAnswer).toHaveBeenCalledWith("old", "yes");
    expect(await screen.findByText("Thanks!")).toBeInTheDocument();
  });

  it("us16_results_include_the_previous_cue_prompt_when_given", () => {
    const { rerender } = render(<ResultsView result={passedResult({ previous_cue_prompt: { analysis_id: "old", cue: "Brace hard", lift: "squat" } })} onFeedback={vi.fn()} />);
    expect(screen.getByText(/your cue was “Brace hard”/)).toBeInTheDocument();
    rerender(<ResultsView result={passedResult()} onFeedback={vi.fn()} />);
    expect(screen.queryByText(/your cue was/)).not.toBeInTheDocument();
  });
});
