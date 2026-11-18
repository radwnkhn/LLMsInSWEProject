import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { UploadForm } from "@/components/UploadForm";
import { videoFile } from "@/test/fixtures";

beforeEach(() => {
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:preview"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function prepare(upload = vi.fn().mockResolvedValue({ analysis_id: "a1" })) {
  render(<UploadForm upload={upload} readDuration={async () => 10} initialLift="squat" />);
  await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile());
  await screen.findByRole("button", { name: "Choose a segment" });
  return upload;
}

it("us04_full_video_is_the_default_without_automatic_cuts", async () => {
  const upload = await prepare();
  expect(screen.getByText(/Full video: 10.0 seconds/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Upload" }));
  expect(upload.mock.calls[0][0].trim).toBeUndefined();
});

it("us04_start_and_end_controls_preview_and_upload_only_the_chosen_range", async () => {
  const upload = await prepare();
  await userEvent.click(screen.getByRole("button", { name: "Choose a segment" }));
  fireEvent.change(screen.getByRole("slider", { name: "Segment start" }), { target: { value: "2" } });
  fireEvent.change(screen.getByRole("slider", { name: "Segment end" }), { target: { value: "8" } });
  expect(screen.getByText("Selected: 6.0 seconds (2.0–8.0s)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Preview selection" }));
  const video = screen.getByLabelText("Video preview") as HTMLVideoElement;
  expect(video.currentTime).toBe(2);
  expect(video.play).toHaveBeenCalled();
  video.currentTime = 8;
  fireEvent.timeUpdate(video);
  expect(video.pause).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Upload" }));
  expect(upload.mock.calls[0][0].trim).toEqual({ start: 2, end: 8 });
});

it("us04_reset_restores_full_video_and_changing_files_discards_the_selection", async () => {
  const upload = await prepare();
  await userEvent.click(screen.getByRole("button", { name: "Choose a segment" }));
  fireEvent.change(screen.getByRole("slider", { name: "Segment start" }), { target: { value: "2" } });
  await userEvent.click(screen.getByRole("button", { name: "Reset to full video" }));
  expect(screen.getByText(/Full video: 10.0 seconds/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Choose a segment" }));
  await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile("other.mp4"));
  await screen.findByText(/Full video: 10.0 seconds/);
  await userEvent.click(screen.getByRole("button", { name: "Upload" }));
  expect(upload.mock.calls[0][0].trim).toBeUndefined();
});

it("us04_invalid_bounds_block_upload_and_retry_preserves_valid_bounds", async () => {
  const upload = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ analysis_id: "a1" });
  await prepare(upload);
  await userEvent.click(screen.getByRole("button", { name: "Choose a segment" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Start time (seconds)" }), { target: { value: "10" } });
  expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
  fireEvent.change(screen.getByRole("spinbutton", { name: "Start time (seconds)" }), { target: { value: "2" } });
  await userEvent.click(screen.getByRole("button", { name: "Upload" }));
  await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
  await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
  expect(upload.mock.calls[1][0].trim).toEqual({ start: 2, end: 10 });
});
