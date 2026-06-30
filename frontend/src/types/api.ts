export type ThemeMode = "light" | "dark" | "system";
export type LanguageCode = "en" | "ar";
export type ProviderName =
  | "openai"
  | "gemini"
  | "deepseek"
  | "ollama"
  | "groq";

export interface InstructorProfile {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  instructor: InstructorProfile;
}

export interface Preference {
  id: string;
  instructor_id: string;
  language: LanguageCode;
  theme: ThemeMode;
}

export interface ProviderConfig {
  id: string;
  instructor_id: string;
  provider_name: ProviderName;
  model_name: string;
  is_active: boolean;
  is_default: boolean;
  daily_request_limit: number | null;
  monthly_request_limit: number | null;
  max_files_per_batch: number | null;
  max_file_size_mb: number | null;
  max_tokens_per_request: number | null;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderUsageSummary {
  provider_name: string;
  requests_today: number;
  requests_this_month: number;
  failures_this_month: number;
  blocked_this_month: number;
  tokens_input_this_month: number;
  tokens_output_this_month: number;
}

export interface AssignmentGroup {
  id: string;
  instructor_id: string;
  name: string;
  description: string | null;
  grade_scale: number;
  enable_auto_score_adjustment: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  criteria?: EvaluationCriterion[];
  submissions_count?: number;
  weights_total?: number;
  ready_for_evaluation?: boolean;
}

export interface EvaluationCriterion {
  id: string;
  group_id: string;
  name: string;
  weight: number;
  description: string | null;
  is_manual: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export type SubmissionStatus =
  | "pending"
  | "queued"
  | "processing"
  | "partially_processed"
  | "completed"
  | "failed";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface Submission {
  id: string;
  group_id: string;
  upload_batch_id: string | null;
  file_path: string;
  original_filename: string;
  student_id: string;
  status: SubmissionStatus;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface DashboardSummary {
  total_groups: number;
  total_submissions: number;
  pending_submissions: number;
  completed_submissions: number;
  failed_submissions: number;
  completed_evaluations: number;
  average_adjusted_score: number | null;
  evaluations_by_provider: Record<string, number>;
  provider_failures_this_month: number;
  usage_today: number;
  usage_this_month: number;
}

export interface EvaluationSummary {
  id: string;
  submission_id: string;
  submission_filename: string;
  student_id: string | null;
  group_id: string;
  group_name: string;
  grade_scale: number;
  evaluation_number: number;
  is_latest: boolean;
  provider_name: string | null;
  model_name: string | null;
  total_ai_score: number | null;
  final_adjusted_score: number | null;
  ai_feedback: string | null;
  created_at: string;
  provider_config_id: string | null;
}

export interface CriterionScore {
  id: string;
  criterion_id: string;
  criterion_name: string;
  weight: number;
  is_manual: boolean;
  ai_score: number | null;
  manual_score: number | null;
  feedback: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationDetail extends EvaluationSummary {
  raw_ai_response: string | null;
  criterion_scores: CriterionScore[];
}

export interface BatchEvaluationStatus {
  active: boolean;
  cancel_requested: boolean;
  total_count: number;
  processed_count: number;
  completed_count: number;
  failed_count: number;
  remaining_count: number;
  current_submission_id: string | null;
  queued_submission_ids: string[];
  completed_submission_ids: string[];
  failed_submission_ids: string[];
  started_at: string | null;
  finished_at: string | null;
}

export interface SubmissionReportRow {
  submission: Submission;
  grade_scale: number;
  latest_evaluation: EvaluationDetail | null;
}
