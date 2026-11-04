import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { UploadForm, type UploadArgs } from "@/components/UploadForm";
import { ApiError } from "@/lib/api";
import { videoFile } from "@/test/fixtures";

async function chooseLiftAndFile(file = videoFile()) {
  await userEvent.click(screen.getByLabelText("Squat"));
  await userEvent.click(screen.getByRole("button", { name: "Got it" }));
  await userEvent.upload(screen.getByLabelText("Video of your set"), file);
}

describe("US-04 upload a set video from my phone", () => {
  it("us04_file_input_accepts_videos_from_camera_or_library", () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    const input = screen.getByLabelText("Video of your set");
    expect(input).toHaveAttribute("type", "file");
    expect(input.getAttribute("accept")).toContain("video/mp4");
    expect(input.getAttribute("accept")).toContain("video/quicktime");
  });

  it("us04_wrong_type_rejected_before_uploading", async () => {
    const upload = vi.fn();
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    await userEvent.click(screen.getByLabelText("Squat"));
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await userEvent.upload(screen.getByLabelText("Video of your set"), videoFile("set.avi", "video/x-msvideo"), { applyAccept: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("Please upload an MP4 or MOV video");
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
    expect(upload).not.toHaveBeenCalled();
  });

  it("us04_too_long_video_rejected_with_the_limit", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 75} />);
    await chooseLiftAndFile();
    expect(await screen.findByRole("alert")).toHaveTextContent("Videos must be 60 seconds or shorter");
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
  });

  it("us04_too_large_video_rejected_with_the_limit", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => 10} />);
    await chooseLiftAndFile(videoFile("set.mp4", "video/mp4", 201 * 1024 * 1024));
    expect(await screen.findByRole("alert")).toHaveTextContent("Videos must be 200 MB or smaller");
  });

  it("us04_unreadable_duration_is_left_to_the_server", async () => {
    render(<UploadForm upload={vi.fn()} readDuration={async () => { throw new Error("no metadata"); }} />);
    await chooseLiftAndFile();
    expect(screen.getByRole("button", { name: "Upload" })).toBeEnabled();
  });

  it("us04_progress_is_shown_as_a_percentage", async () => {
    let report: (p: number) => void = () => {};
    const upload = vi.fn((args: UploadArgs) => { report = args.onProgress; return new Promise<{ analysis_id: string }>(() => {}); });
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    await chooseLiftAndFile();
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    act(() => report(42));
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");
    act(() => report(100));
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("us04_success_hands_back_the_analysis_id", async () => {
    const onUploaded = vi.fn();
    render(<UploadForm upload={vi.fn().mockResolvedValue({ analysis_id: "a9" })} readDuration={async () => 10} onUploaded={onUploaded} />);
    await chooseLiftAndFile();
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(onUploaded).toHaveBeenCalledWith("a9");
  });

  it("us04_failed_upload_shows_error_with_retry_that_reuses_the_file", async () => {
    const upload = vi.fn()
      .mockRejectedValueOnce(new ApiError(0, "Network error"))
      .mockResolvedValueOnce({ analysis_id: "a1" });
    const onUploaded = vi.fn();
    const file = videoFile();
    render(<UploadForm upload={upload} readDuration={async () => 10} onUploaded={onUploaded} />);
    await chooseLiftAndFile(file);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Upload failed");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(upload).toHaveBeenCalledTimes(2);
    expect(upload.mock.calls[1][0].file).toBe(file);
    expect(upload.mock.calls[1][0].lift).toBe("squat");
    expect(onUploaded).toHaveBeenCalledWith("a1");
  });

  it("us04_server_rejection_message_is_shown", async () => {
    const upload = vi.fn().mockRejectedValue(new ApiError(422, "Videos must be 60 seconds or shorter"));
    render(<UploadForm upload={upload} readDuration={async () => 10} />);
    await chooseLiftAndFile();
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Videos must be 60 seconds or shorter");
  });
});
