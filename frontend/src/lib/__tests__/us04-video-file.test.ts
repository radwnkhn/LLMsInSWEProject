import { describe, expect, it } from "vitest";

import {
  DURATION_MESSAGE, MAX_DURATION_SECONDS, MAX_SIZE_BYTES, SIZE_MESSAGE, TYPE_MESSAGE, checkVideoType, validateVideoFile,
} from "@/lib/videoFile";
import { videoFile } from "@/test/fixtures";

describe("US-04 video file checks before uploading", () => {
  it("us04_limits_and_messages", () => {
    expect(MAX_DURATION_SECONDS).toBe(60);
    expect(MAX_SIZE_BYTES).toBe(200 * 1024 * 1024);
    expect(TYPE_MESSAGE).toBe("Please upload an MP4 or MOV video");
    expect(DURATION_MESSAGE).toBe("Videos must be 60 seconds or shorter");
    expect(SIZE_MESSAGE).toBe("Videos must be 200 MB or smaller");
  });

  it.each([
    ["set.mp4", "video/mp4"],
    ["IMG_0042.MOV", "video/quicktime"],
    ["clip.mov", ""],
    ["clip.MP4", "application/octet-stream"],
  ])("us04_accepts_mp4_and_mov_%s", (name, type) => {
    expect(checkVideoType(videoFile(name, type))).toBeNull();
  });

  it.each([
    ["set.avi", "video/x-msvideo"],
    ["set.webm", "video/webm"],
    ["photo.jpg", "image/jpeg"],
    ["set.mp4.exe", "application/octet-stream"],
    ["noextension", ""],
  ])("us04_rejects_other_types_%s", (name, type) => {
    expect(checkVideoType(videoFile(name, type))).toBe(TYPE_MESSAGE);
  });

  it("us04_rejects_videos_longer_than_60_seconds", () => {
    expect(validateVideoFile(videoFile(), 60.4)).toBe(DURATION_MESSAGE);
    expect(validateVideoFile(videoFile(), 60)).toBeNull();
  });

  it("us04_rejects_videos_larger_than_200_mb", () => {
    expect(validateVideoFile(videoFile("set.mp4", "video/mp4", MAX_SIZE_BYTES + 1), 10)).toBe(SIZE_MESSAGE);
    expect(validateVideoFile(videoFile("set.mp4", "video/mp4", MAX_SIZE_BYTES), 10)).toBeNull();
  });

  it("us04_type_is_checked_first", () => {
    expect(validateVideoFile(videoFile("set.avi", "video/x-msvideo", MAX_SIZE_BYTES + 1), 90)).toBe(TYPE_MESSAGE);
  });
});
