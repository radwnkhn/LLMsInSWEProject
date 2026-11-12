// US-28 added overhead_press and romanian_deadlift.
export type Lift = "squat" | "deadlift" | "bench_press" | "overhead_press" | "romanian_deadlift";
export type TriedCue = "yes" | "no" | "not_yet";
export type FinalStatus = "passed_first_try" | "passed_after_retry" | "fallback" | "unanalyzable";
export type JobStatus = "queued" | "processing" | "done" | "failed";
export type ProcessingStage = "measuring" | "writing_feedback" | "checking";

export type Session = { access_token: string; user: { id: string; email: string; is_admin: boolean; is_trainer?: boolean } };

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
  upload_id?: string;
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

export type AnalysisComparison = {
  older: AnalysisResult;
  newer: AnalysisResult;
  metrics: {
    metric: string; label: string; unit: string; aggregation: "Minimum" | "Maximum" | "Count";
    older: number | null; newer: number | null;
  }[];
  fault_comparison: {
    fault_id: string | null; title: string | null;
    status: "still_present" | "not_detected" | "not_measured" | "no_previous_fault" | "unavailable";
    older_reps: number[]; newer_reps: number[];
  };
};

// US-25: the saved fault list, managed on /admin/faults.
export type FaultCategory = "safety" | "technique";
export type FaultDirection = "above" | "below";

export type AdminFault = {
  lift: Lift;
  id: string;
  name: string;
  short_name: string;
  category: FaultCategory;
  safety: boolean;
  metric: string;
  metric_label: string;
  threshold: number;
  direction: FaultDirection;
  unit: string;
  enabled: boolean;
  threshold_min?: number; // US-24: the allowed range for this fault's threshold
  threshold_max?: number;
};

export type FaultMetric = { metric: string; label: string; unit: string };

export type AdminFaultLift = { lift: Lift; lift_label: string; faults: AdminFault[]; metrics: FaultMetric[] };

export type FaultEdit = Partial<Pick<AdminFault, "name" | "short_name" | "enabled" | "threshold">>;

// US-24: one logged threshold change, newest first on /admin/faults.
export type ThresholdChange = {
  lift: Lift;
  lift_label: string;
  fault_id: string;
  fault_name: string;
  unit: string;
  old_threshold: number;
  new_threshold: number;
  changed_by_email: string | null; // null once the admin's account is deleted
  changed_at: string;
};

export type NewFault = Pick<AdminFault, "lift" | "id" | "name" | "short_name" | "category" | "metric" | "threshold" | "direction">;

export type AdminAttempt = {
  attempt_number: number;
  output_text: string;
  input_tokens: number;
  output_tokens: number;
  passed: boolean;
  errors: { code: string; message: string }[];
  provider: string | null; // US-26; null for attempts saved before usage tracking
  model: string | null;
  cost: number | null; // dollars; null when the model has no price
};

export type AnalysisUsage = { input_tokens: number; output_tokens: number; cost: number | null; unknown_cost_attempts: number };

export type CostSummary = {
  start: string;
  end: string;
  analysis_count: number;
  attempt_count: number;
  retry_attempt_count: number;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  average_cost: number | null;
  retry_cost: number;
  retry_share: number | null;
  unknown_cost_attempts: number;
};

// US-27: usage over time and moderation.
export type UsageReport = {
  start: string;
  end: string;
  days: { date: string; signups: number; uploads: number }[];
  totals: { signups: number; uploads: number };
  removals: number;
};

export type AdminUpload = {
  upload_id: string;
  analysis_id: string | null;
  created_at: string;
  lift: Lift;
  lift_label: string;
  user_email: string;
  filename: string;
  status_label: string;
};

export type UploadFilters = { start?: string; end?: string; lift?: string };

export type RemovalReason = "off_topic" | "inappropriate" | "other";

export type ModerationEntry = {
  id: string;
  upload_id: string;
  analysis_ids: string[];
  lift: Lift;
  owner_email: string | null;
  removed_by_email: string | null;
  reason: RemovalReason;
  reason_label: string;
  note: string | null;
  removed_at: string;
};

export type AdminDetail = {
  analysis: AdminRow;
  video_url: string | null;
  measurements: RepMeasurementView[];
  attempts: AdminAttempt[];
  usage: AnalysisUsage;
  result: AnalysisResult | null;
};

// US-22: blind trainer grading.
export type Verdict = "correct" | "partly_correct" | "wrong";
export type GradingStatus = "waiting" | "answered" | "graded";
/** A fault picked by a trainer or reported by us; fault_id null is "No major issue". */
export type FaultChoice = { fault_id: string | null; name: string };

export type Trainer = { id: string; email: string };

export type AdminGradingAssignment = {
  assignment_id: string;
  analysis_id: string;
  lift: Lift;
  lift_label: string;
  trainer_email: string | null;
  assigned_at: string;
  graded_at: string | null;
  status: GradingStatus;
  status_label: string;
  trainer_answer: FaultChoice | null;
  our_fault: FaultChoice;
  verdict: Verdict | null;
  verdict_label: string | null;
};

export type GradingAssignResult = { requested: number; assigned: number; items: AdminGradingAssignment[] };

export type TrainerAssignmentItem = {
  assignment_id: string;
  lift: Lift;
  lift_label: string;
  assigned_at: string;
  status: GradingStatus;
  status_label: string;
};

type GradedFault = { fault_id: string; title: string; reps: number[] };

/** The coaching the lifter was shown; trainers only get it after recording their own top fault. */
export type OurFeedback = {
  top_fix: GradedFault | null;
  cue: string | null;
  explanation: string | null;
  other_faults: GradedFault[];
  no_major_issues: boolean;
};

export type TrainerAssignment = Omit<TrainerAssignmentItem, "assigned_at"> & {
  assigned_at?: string;
  video_url: string;
  fault_options: FaultChoice[];
  trainer_answer: FaultChoice | null;
  our_feedback: OurFeedback | null;
  verdict: Verdict | null;
  verdict_label: string | null;
};

// US-23: the hypothesis metrics dashboard.
export type MetricKey = "trainer_agreement" | "helpful_ratings" | "cue_tried" | "seven_day_return";
export type MetricStatus = "on_target" | "below_target" | "failing" | "no_data";

export type HypothesisMetric = {
  key: MetricKey;
  label: string;
  value: number | null; // a share from 0 to 1; null with no data
  hits: number;
  count: number;
  basis: string; // e.g. "3 graded sets"
  target: number;
  fail_below: number;
  status: MetricStatus;
  status_label: string;
};

export type MetricsReport = { start: string; end: string; metrics: HypothesisMetric[]; pending_returns: number };
