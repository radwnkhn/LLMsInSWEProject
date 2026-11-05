import type { AnalysisResult } from "@/lib/types";

/** A finished analysis as GET /analyses/{id} returns it: hips rose early on reps 4 and 5. */
export function passedResult(overrides: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    analysis_id: "a1",
    created_at: "2026-11-03T15:04:05Z",
    status: "done",
    final_status: "passed_first_try",
    lift: "squat",
    lift_label: "Squat",
    camera_angle: "side",
    rep_count: 5,
    unanalyzable_reason: null,
    top_fix: { fault_id: "hips_rise_early", title: "Hips rise before your shoulders", category: "technique", safety: false, reps: [4, 5] },
    cue: "Drive your chest up with your hips",
    explanation: "On reps 4 and 5 your torso tipped forward as you stood up.",
    no_major_issues: false,
    other_faults: [
      { fault_id: "bar_path_drift", title: "Bar drifts forward and back", category: "technique", safety: false, reps: [4] },
    ],
    not_measured: [{ check: "knee_cave", name: "Knees cave inward", reason: "needs a front view" }],
    rep_breakdown: {
      rows: [1, 2, 3, 4, 5].map((rep) => ({
        rep,
        start_time: (rep - 1) * 1.73,
        end_time: rep * 1.73 - 0.1,
        faults: rep >= 4 ? ["Hips rise before your shoulders"] : [],
        clean: rep < 4,
      })),
      fatigue_note: "Form broke down late in the set, likely from fatigue.",
    },
    measurements: [],
    annotated_frame: {
      rep: 4, frame_index: 200, timestamp: 6.67, rep_start_time: 5.53, metric: "torso_lean_increase_deg",
      value: 14.2, label: "Torso +14°", image_url: "https://storage.test/frame.png?token=abc",
    },
    professional_message: null,
    fallback_note: null,
    video_url: "https://storage.test/video.mp4?token=abc",
    previous_cue_prompt: null,
    feedback: null,
    error: null,
    ...overrides,
  };
}

export function fallbackResult(): AnalysisResult {
  return passedResult({
    final_status: "fallback",
    top_fix: null,
    cue: null,
    explanation: null,
    other_faults: [],
    annotated_frame: null,
    no_major_issues: false,
    fallback_note: "Coaching feedback isn't available for this video. Here are your measurements.",
  });
}

export function unanalyzableResult(reason = "Couldn't analyze: no person found"): AnalysisResult {
  return passedResult({
    final_status: "unanalyzable",
    unanalyzable_reason: reason,
    rep_count: 0,
    top_fix: null,
    cue: null,
    explanation: null,
    other_faults: [],
    not_measured: [],
    rep_breakdown: null,
    annotated_frame: null,
    no_major_issues: false,
  });
}

export function videoFile(name = "set.mp4", type = "video/mp4", size = 1024): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}
