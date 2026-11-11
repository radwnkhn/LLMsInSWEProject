import type {
  AdminDetail, AdminFault, AdminFaultLift, AdminRow, AnalysisComparison, AnalysisResult, CostSummary, FaultEdit,
  FeedbackAnswer, HistoryItem, Lift, NewFault, Session, TriedCue,
} from "@/lib/types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

type Detail = string | { msg: string }[] | undefined;

function detailText(detail: Detail, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ");
  return fallback;
}

async function request<T>(path: string, { method = "GET", body, token, signal }: {
  method?: string; body?: unknown; token?: string | null; signal?: AbortSignal;
} = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      signal,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Network error");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, detailText(data.detail, res.statusText));
  return data as T;
}

export const api = {
  signup: (email: string, password: string) => request<Session>("/auth/signup", { method: "POST", body: { email, password } }),
  login: (email: string, password: string) => request<Session>("/auth/login", { method: "POST", body: { email, password } }),
  logout: (token: string) => request<void>("/auth/logout", { method: "POST", token }),
  analysis: (id: string, token: string | null, signal?: AbortSignal) => request<AnalysisResult>(`/analyses/${encodeURIComponent(id)}`, { token, signal }),
  retryAnalysis: (id: string, token: string | null) => request<{ analysis_id: string; status: "queued" }>(
    `/analyses/${encodeURIComponent(id)}/retry`, { method: "POST", token }),
  sendFeedback: (id: string, answer: Partial<FeedbackAnswer>, token: string | null) => {
    const body: { rating?: number; tried_cue?: TriedCue } = {};
    if (answer.rating != null) body.rating = answer.rating;
    if (answer.tried_cue != null) body.tried_cue = answer.tried_cue;
    return request<FeedbackAnswer>(`/analyses/${encodeURIComponent(id)}/feedback`, { method: "POST", body, token });
  },
  history: (token: string | null) => request<{ items: HistoryItem[] }>("/history", { token }),
  deleteUpload: (uploadId: string, token: string | null) => request<void>(`/uploads/${encodeURIComponent(uploadId)}`,
    { method: "DELETE", token, body: { confirmed: true } }),
  deleteAccount: (token: string | null) => request<void>("/account", { method: "DELETE", token, body: { confirmed: true } }),
  comparison: (firstId: string, secondId: string, token: string | null, signal?: AbortSignal) => request<AnalysisComparison>(
    `/comparisons?${new URLSearchParams({ first_id: firstId, second_id: secondId })}`, { token, signal }),
  adminAnalyses: (token: string | null) => request<{ items: AdminRow[] }>("/admin/analyses", { token }),
  adminAnalysis: (id: string, token: string | null) => request<AdminDetail>(`/admin/analyses/${encodeURIComponent(id)}`, { token }),
  adminCosts: (start: string | null, end: string | null, token: string | null) => {
    const range = new URLSearchParams();
    if (start) range.set("start", start);
    if (end) range.set("end", end);
    const query = range.toString();
    return request<CostSummary>(`/admin/costs${query ? `?${query}` : ""}`, { token });
  },
  adminErrors: (token: string | null) => request<{ counts: Record<string, number> }>("/admin/validator-errors", { token }),
  adminFaults: (token: string | null) => request<{ lifts: AdminFaultLift[] }>("/admin/faults", { token }),
  updateFault: (lift: string, id: string, edit: FaultEdit, token: string | null) => request<AdminFault>(
    `/admin/faults/${encodeURIComponent(lift)}/${encodeURIComponent(id)}`, { method: "PATCH", body: edit, token }),
  addFault: (fault: NewFault, token: string | null) => request<AdminFault>("/admin/faults", { method: "POST", body: fault, token }),
  health: () => request<{ status: string }>("/health"),
};

export type UploadResponse = { upload_id: string; analysis_id: string; status: string };

/** Uploads with XMLHttpRequest, because fetch can't report upload progress. */
export function uploadVideo({ file, lift, note, token, onProgress }: {
  file: File; lift: Lift | string; note: string; token: string | null; onProgress: (percent: number) => void;
}): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/uploads`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let data: { detail?: Detail } & Partial<UploadResponse> = {};
      try {
        data = JSON.parse(xhr.responseText || "{}");
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as UploadResponse);
      else reject(new ApiError(xhr.status, detailText(data.detail, "Upload failed")));
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error"));
    const form = new FormData();
    form.append("file", file);
    form.append("lift", lift);
    if (note) form.append("note", note);
    xhr.send(form);
  });
}
