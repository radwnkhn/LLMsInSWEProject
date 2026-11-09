export type Lift = "squat" | "deadlift" | "bench_press";
export type TriedCue = "yes" | "no" | "not_yet";
export type FinalStatus = "passed_first_try" | "passed_after_retry" | "fallback" | "unanalyzable";
export type JobStatus = "queued" | "processing" | "done" | "failed";
export type ProcessingStage = "measuring" | "writing_feedback" | "checking";

export type Session = { access_token: string; user: { id: string; email: string; is_admin: boolean } };

export type FaultView = {
  fault_id: string;
  title: string;
  category: "safety" | "technique";
  safety: boolean;
  reps: number[];
};

export type NotMeasuredCheck = { check: string; name: string; reason: string };

export type RepRow = { rep: number; start_time: number; end_time: number; faults: string[]; clean: boolean };
export type RepBreakdownData = { rows: RepRow[]; fatigue_note: string | null };

export type AnnotatedFrameData = {
  rep: number;
  frame_index: number;
  timestamp: number;
  rep_start_time: number;
  metric: string;
  value: number;
  label: string;
  image_url: string;
};

export type RepMeasurementView = {
  rep: number;
  start_time: number;
  end_time: number;
  metrics: Record<string, number | null>;
  depth_reached: boolean | null;
};

export type FeedbackAnswer = { rating: number | null; tried_cue: TriedCue | null };
export type PreviousCuePromptData = { analysis_id: string; cue: string; lift: Lift };

export type AnalysisResult = {
  analysis_id: string;
  created_at: string;
  status: JobStatus;
  processing_stage: ProcessingStage | null;
  final_status: FinalStatus | null;
  lift: Lift;
  lift_label: string;
  camera_angle: string | null;
  rep_count: number | null;
  unanalyzable_reason: string | null;
  top_fix: FaultView | null;
  cue: string | null;
  explanation: string | null;
  no_major_issues: boolean;
  other_faults: FaultView[];
  not_measured: NotMeasuredCheck[];
  rep_breakdown: RepBreakdownData | null;
  measurements: RepMeasurementView[];
  annotated_frame: AnnotatedFrameData | null;
  professional_message: string | null;
  fallback_note: string | null;
  video_url: string | null;
  previous_cue_prompt: PreviousCuePromptData | null;
  feedback: FeedbackAnswer | null;
  error: string | null;
};

export type HistoryItem = {
  analysis_id: string;
  created_at: string;
  lift: Lift;
  lift_label: string;
  rep_count: number | null;
  top_fix_title: string | null;
  status: JobStatus;
  final_status: FinalStatus | null;
  status_label: string;
};

export type AdminRow = {
  analysis_id: string;
  created_at: string;
  user_email: string;
  lift: Lift;
  lift_label: string;
  attempt_count: number;
  final_status: FinalStatus | null;
  final_status_label: string;
};

export type AdminAttempt = {
  attempt_number: number;
  output_text: string;
  input_tokens: number;
  output_tokens: number;
  passed: boolean;
  errors: { code: string; message: string }[];
};

export type AdminDetail = {
  analysis: AdminRow;
  video_url: string | null;
  measurements: RepMeasurementView[];
  attempts: AdminAttempt[];
  result: AnalysisResult | null;
};
