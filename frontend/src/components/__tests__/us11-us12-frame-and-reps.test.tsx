import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnnotatedFrame } from "@/components/AnnotatedFrame";
import { RepBreakdown } from "@/components/RepBreakdown";
import { formatTime } from "@/lib/format";
import { passedResult } from "@/test/fixtures";

describe("US-11 annotated frame", () => {
  const frame = passedResult().annotated_frame!;

  it("us11_frame_image_and_caption_match_the_stored_values", () => {
    render(<AnnotatedFrame frame={frame} onPlayFrom={vi.fn()} />);
    expect(screen.getByRole("img", { name: "Rep 4 at 0:06.7 with the measurement Torso +14°" })).toHaveAttribute("src", frame.image_url);
    const caption = screen.getByText(/Rep 4/);
    expect(caption).toHaveTextContent("Rep 4 · 0:06.7 · Torso +14°");
  });

  it("us11_tapping_the_frame_plays_from_the_start_of_that_rep", async () => {
    const onPlayFrom = vi.fn();
    render(<AnnotatedFrame frame={frame} onPlayFrom={onPlayFrom} />);
    await userEvent.click(screen.getByRole("button", { name: /play rep 4/i }));
    expect(onPlayFrom).toHaveBeenCalledWith(5.53);
  });

  it("us11_time_format", () => {
    expect(formatTime(6.67)).toBe("0:06.7");
    expect(formatTime(75.04)).toBe("1:15.0");
    expect(formatTime(0)).toBe("0:00.0");
  });
});

describe("US-12 rep-by-rep breakdown", () => {
  const breakdown = passedResult().rep_breakdown!;

  it("us12_one_row_per_rep_in_order", () => {
    render(<RepBreakdown breakdown={breakdown} onSeek={vi.fn()} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(5);
    expect(rows.map((r) => r.getAttribute("aria-label"))).toEqual(["Rep 1", "Rep 2", "Rep 3", "Rep 4", "Rep 5"]);
  });

  it("us12_rows_show_clean_or_their_faults", () => {
    render(<RepBreakdown breakdown={breakdown} onSeek={vi.fn()} />);
    expect(within(screen.getByRole("listitem", { name: "Rep 1" })).getByText("Clean")).toBeInTheDocument();
    const rep4 = screen.getByRole("listitem", { name: "Rep 4" });
    expect(rep4).toHaveTextContent("Hips rise before your shoulders");
    expect(rep4).not.toHaveTextContent("Clean");
  });

  it("us12_fatigue_note_shown_when_present", () => {
    const { rerender } = render(<RepBreakdown breakdown={breakdown} onSeek={vi.fn()} />);
    expect(screen.getByText("Form broke down late in the set, likely from fatigue.")).toBeInTheDocument();
    rerender(<RepBreakdown breakdown={{ ...breakdown, fatigue_note: null }} onSeek={vi.fn()} />);
    expect(screen.queryByText(/likely from fatigue/)).not.toBeInTheDocument();
  });

  it("us12_tapping_a_row_seeks_to_that_rep", async () => {
    const onSeek = vi.fn();
    render(<RepBreakdown breakdown={breakdown} onSeek={onSeek} />);
    await userEvent.click(within(screen.getByRole("listitem", { name: "Rep 3" })).getByRole("button"));
    expect(onSeek).toHaveBeenCalledWith(breakdown.rows[2].start_time);
  });
});
