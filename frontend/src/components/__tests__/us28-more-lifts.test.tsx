import { existsSync } from "node:fs";
import path from "node:path";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilmingGuide } from "@/components/FilmingGuide";
import { LiftPicker } from "@/components/LiftPicker";
import { FILMING_GUIDES } from "@/lib/filming";
import { isLift, liftLabel, liftNoun, LIFTS } from "@/lib/lifts";
import type { Lift } from "@/lib/types";

const NEW_LIFTS = [["overhead_press", "Overhead Press", "overhead press"],
  ["romanian_deadlift", "Romanian Deadlift", "Romanian deadlift"]] as const;

describe("US-28 more lifts", () => {
  it("us28_picker_offers_the_two_new_lifts_after_the_existing_three", () => {
    render(<LiftPicker value={null} onChange={vi.fn()} />);
    expect(screen.getAllByRole("radio").map((o) => o.closest("label")?.textContent?.trim()))
      .toEqual(["Squat", "Deadlift", "Bench Press", "Overhead Press", "Romanian Deadlift"]);
  });

  it.each(NEW_LIFTS)("us28_picking_%s_reports_its_id", async (id, label) => {
    const onChange = vi.fn();
    render(<LiftPicker value={null} onChange={onChange} />);
    await userEvent.click(screen.getByLabelText(label));
    expect(onChange).toHaveBeenCalledWith(id);
  });

  it.each(NEW_LIFTS)("us28_%s_has_a_label_and_noun", (id, label, noun) => {
    expect(isLift(id)).toBe(true);
    expect(liftLabel(id as Lift)).toBe(label);
    expect(liftNoun(id as Lift)).toBe(noun);
    expect(LIFTS.map((l) => l.id)).toContain(id);
  });

  it.each(NEW_LIFTS)("us28_%s_filming_guide_covers_view_phone_height_distance_and_framing", (id) => {
    const tips = (FILMING_GUIDES as Record<string, { tips: string[] }>)[id].tips.join(" ");
    expect(tips).toMatch(/side view/i);
    expect(tips).toMatch(/height/i);
    expect(tips).toMatch(/\d+ m \(\d+ ft\) away/);
    expect(tips).toMatch(/in frame/i);
  });

  it.each(NEW_LIFTS)("us28_%s_filming_guide_has_its_own_example_frame", (id, label) => {
    const guide = (FILMING_GUIDES as Record<string, { image: string; imageAlt: string }>)[id];
    expect(guide.image).toBe(`/framing/${id}.svg`);
    expect(existsSync(path.join(process.cwd(), "public", guide.image))).toBe(true);
    render(<FilmingGuide lift={id as Lift} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: `Filming tips: ${label}` })).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("alt", `Example of correct framing for a ${label.toLowerCase()}`);
  });

  it("us28_new_lift_tips_differ_from_the_existing_lifts", () => {
    const guides = FILMING_GUIDES as Record<string, { tips: string[] }>;
    expect(guides.overhead_press.tips).not.toEqual(guides.bench_press.tips);
    expect(guides.romanian_deadlift.tips).not.toEqual(guides.deadlift.tips);
  });
});
