import { apiRequest } from "@/lib/api-client";
import type { PaginatedResponse, Submission, SubmissionReportRow, SubmissionStatus } from "@/types/api";

type FetchSubmissionsParams = {
  groupId: string;
  page?: number;
  pageSize?: number;
  missingStudentIdOnly?: boolean;
};

type FetchSubmissionReportParams = {
  groupId: string;
  search?: string;
  page?: number;
  pageSize?: number;
};

function buildQueryString(params: Record<string, string | number | boolean | undefined>) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });
  return searchParams.toString();
}

export function fetchSubmissions({
  groupId,
  page = 1,
  pageSize = 25,
  missingStudentIdOnly = false,
}: FetchSubmissionsParams) {
  const query = buildQueryString({
    group_id: groupId,
    page,
    page_size: pageSize,
    missing_student_id_only: missingStudentIdOnly,
  });
  return apiRequest<PaginatedResponse<Submission>>(`/submissions?${query}`);
}

export function fetchSubmissionReport({
  groupId,
  search = "",
  page = 1,
  pageSize = 25,
}: FetchSubmissionReportParams) {
  const query = buildQueryString({
    group_id: groupId,
    search,
    page,
    page_size: pageSize,
  });
  return apiRequest<PaginatedResponse<SubmissionReportRow>>(`/submissions/report?${query}`);
}

export function fetchEvaluatableSubmissionIds(groupId: string) {
  const query = buildQueryString({ group_id: groupId });
  return apiRequest<{ items: string[] }>(`/submissions/evaluatable-ids?${query}`);
}

export function uploadSubmissions(formData: FormData) {
  return apiRequest<{
    batch: { id: string };
    results: Array<{
      original_filename: string;
      source_upload_index?: number | null;
      source_upload_filename?: string | null;
      from_archive?: boolean;
      student_id?: string | null;
      accepted: boolean;
      reason?: string | null;
      submission_id?: string | null;
      status?: SubmissionStatus | null;
      needs_student_id?: boolean;
      is_duplicate?: boolean;
      duplicate_reasons?: string[];
      has_existing_match?: boolean;
      existing_duplicate_reasons?: string[];
      existing_submission_id?: string | null;
      existing_submission_evaluated?: boolean;
    }>;
  }>("/submissions/upload", {
    method: "POST",
    body: formData,
  });
}

export function previewSubmissionStudentIds(formData: FormData) {
  return apiRequest<{
    results: Array<{
      original_filename: string;
      source_upload_index?: number | null;
      source_upload_filename?: string | null;
      from_archive?: boolean;
      student_id?: string | null;
      accepted: boolean;
      reason?: string | null;
      needs_student_id?: boolean;
      is_duplicate?: boolean;
      duplicate_reasons?: string[];
      has_existing_match?: boolean;
      existing_duplicate_reasons?: string[];
      existing_submission_id?: string | null;
      existing_submission_evaluated?: boolean;
    }>;
  }>("/submissions/preview-student-ids", {
    method: "POST",
    body: formData,
  });
}

export function updateSubmissionStudentId(submissionId: string, studentId: string) {
  return apiRequest<Submission>(`/submissions/${submissionId}/student-id`, {
    method: "PATCH",
    bodyJson: { student_id: studentId },
  });
}

export function canEvaluateSubmission(status: SubmissionStatus, studentId?: string | null) {
  return Boolean(studentId?.trim()) && (status === "pending" || status === "failed" || status === "queued");
}
