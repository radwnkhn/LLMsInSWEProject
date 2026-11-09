import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, uploadVideo } from "@/lib/api";
import { videoFile } from "@/test/fixtures";

type Listener = (e: { lengthComputable: boolean; loaded: number; total: number }) => void;

class FakeXHR {
  static last: FakeXHR;
  upload = { onprogress: null as Listener | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  status = 0;
  responseText = "";
  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: FormData | null = null;
  constructor() { FakeXHR.last = this; }
  open(method: string, url: string) { this.method = method; this.url = url; }
  setRequestHeader(k: string, v: string) { this.headers[k] = v; }
  send(body: FormData) { this.body = body; }
}

afterEach(() => vi.unstubAllGlobals());

describe("US-04 upload request", () => {
  it("us04_upload_reports_progress_as_a_percentage", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const progress: number[] = [];
    const promise = uploadVideo({ file: videoFile(), lift: "squat", note: "", token: "tok", onProgress: (p) => progress.push(p) });
    const xhr = FakeXHR.last;
    xhr.upload.onprogress!({ lengthComputable: true, loaded: 25, total: 100 });
    xhr.upload.onprogress!({ lengthComputable: true, loaded: 333, total: 1000 });
    xhr.upload.onprogress!({ lengthComputable: true, loaded: 100, total: 100 });
    xhr.status = 201;
    xhr.responseText = JSON.stringify({ analysis_id: "a1", upload_id: "u1", status: "queued" });
    xhr.onload!();
    await expect(promise).resolves.toMatchObject({ analysis_id: "a1" });
    expect(progress).toEqual([25, 33, 100]);
  });

  it("us04_upload_sends_file_lift_note_and_token", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const file = videoFile();
    const promise = uploadVideo({ file, lift: "bench_press", note: "felt good", token: "tok", onProgress: () => {} });
    const xhr = FakeXHR.last;
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toMatch(/\/uploads$/);
    expect(xhr.headers.Authorization).toBe("Bearer tok");
    expect(xhr.body!.get("lift")).toBe("bench_press");
    expect(xhr.body!.get("note")).toBe("felt good");
    expect(xhr.body!.get("file")).toBe(file);
    xhr.status = 201;
    xhr.responseText = JSON.stringify({ analysis_id: "a1" });
    xhr.onload!();
    await promise;
  });

  it("us04_upload_rejects_with_the_server_message", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const promise = uploadVideo({ file: videoFile(), lift: "squat", note: "", token: "tok", onProgress: () => {} });
    FakeXHR.last.status = 415;
    FakeXHR.last.responseText = JSON.stringify({ detail: "Please upload an MP4 or MOV video" });
    FakeXHR.last.onload!();
    await expect(promise).rejects.toEqual(new ApiError(415, "Please upload an MP4 or MOV video"));
  });

  it("us04_upload_rejects_on_network_error", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const promise = uploadVideo({ file: videoFile(), lift: "squat", note: "", token: "tok", onProgress: () => {} });
    FakeXHR.last.onerror!();
    await expect(promise).rejects.toBeInstanceOf(ApiError);
  });
});
