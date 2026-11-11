import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LiftPicker } from "@/components/LiftPicker";
import { UploadForm } from "@/components/UploadForm";
import { videoFile } from "@/test/fixtures";

const okUpload = () => vi.fn().mockResolvedValue({ analysis_id: "a1" });

describe("US-02 choose the lift before uploading", () => {
  it("us02_lift_picker_offers_the_supported_lifts", () => {
    // US-28 added Overhead Press and Romanian Deadlift after the original three ("exactly three" before US-28).
    render(<LiftPicker value={null} onChange={vi.fn()} />);
    const options = screen.getAllByRole("radio");
    expect(options.map((o) => o.closest("label")?.textContent?.trim()).slice(0, 3)).toEqual(["Squat", "Deadlift", "Bench Press"]);
  });

  it("us02_lift_picker_reports_the_lift_id", async () => {
    const onChange = vi.fn();
    render(<LiftPicker value={null} onChange={onChange} />);
    await userEvent.click(screen.getByLabelText("Bench Press"));
    expect(onChange).toHaveBeenCalledWith("bench_press");
  });

  it("us02_upload_button_disabled_until_lift_selected", async () => {
    render(<UploadForm upload={okUpload()} readDuration={async () => 10} />);
    await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile());
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.getByRole("button", { name: "Upload" })).toBeEnabled();
  });

  it("us02_upload_button_disabled_without_a_video_even_with_a_lift", async () => {
    render(<UploadForm upload={okUpload()} readDuration={async () => 10} />);
    await userEvent.click(screen.getByLabelText("Deadlift"));
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
  });

  it("us02_selected_lift_is_sent_with_the_upload", async () => {
    const upload = okUpload();
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    await userEvent.click(screen.getByLabelText("Deadlift"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile());
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(upload).toHaveBeenCalledWith(expect.objectContaining({ lift: "deadlift" }));
  });
});
