import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilmingGuide } from "@/components/FilmingGuide";
import { UploadForm } from "@/components/UploadForm";
import { FILMING_GUIDES } from "@/lib/filming";
import { LIFTS } from "@/lib/lifts";

describe("US-03 filming guidance before recording", () => {
  it.each(LIFTS.map((l) => [l.label, l.id] as const))(
    "us03_guide_shows_the_core_tips_for_%s",
    (_label, lift) => {
      render(<FilmingGuide lift={lift} onClose={vi.fn()} />);
      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveTextContent(/side view/i);
      expect(dialog).toHaveTextContent(/hip height/i);
      expect(dialog).toHaveTextContent(/whole body and the bar/i);
    },
  );

  it("us03_guide_tips_are_specific_to_the_lift", () => {
    expect(FILMING_GUIDES.squat.tips).not.toEqual(FILMING_GUIDES.bench_press.tips);
    render(<FilmingGuide lift="bench_press" onClose={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Filming tips: Bench Press" })).toBeInTheDocument();
  });

  it("us03_guide_shows_example_image_of_correct_framing", () => {
    render(<FilmingGuide lift="deadlift" onClose={vi.fn()} />);
    const img = screen.getByRole("img", { name: "Example of correct framing for a deadlift" });
    expect(img).toHaveAttribute("src", expect.stringContaining("/framing/deadlift"));
  });

  it("us03_guide_opens_after_choosing_a_lift", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Squat"));
    expect(screen.getByRole("dialog", { name: "Filming tips: Squat" })).toBeInTheDocument();
  });

  it("us03_guide_can_be_dismissed_and_reopened", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Filming tips" }));
    expect(screen.getByRole("dialog", { name: "Filming tips: Squat" })).toBeInTheDocument();
  });

  it("us03_guide_does_not_reopen_on_its_own_when_changing_lift", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await userEvent.click(screen.getByLabelText("Deadlift"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Filming tips" }));
    expect(screen.getByRole("dialog", { name: "Filming tips: Deadlift" })).toBeInTheDocument();
  });

  it("us03_tips_button_is_disabled_until_a_lift_is_chosen", () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    expect(screen.getByRole("button", { name: "Filming tips" })).toBeDisabled();
  });

  it("us03_guide_open_on_arrival_when_asked_to_refilm", () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} initialLift="squat" initialGuideOpen />);
    expect(screen.getByRole("dialog", { name: "Filming tips: Squat" })).toBeInTheDocument();
  });
});
