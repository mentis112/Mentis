import { apiRequest } from "@/lib/api-client";
import type { BatchEvaluationStatus, EvaluationDetail, EvaluationSummary } from "@/types/api";

export function evaluateSubmission(submissionId: string) {
  return apiRequest<EvaluationDetail>(`/submissions/${submissionId}/evaluate`, {
    method: "POST",
    bodyJson: {},
  });
}

export function fetchSubmissionEvaluations(submissionId: string) {
  return apiRequest<EvaluationSummary[]>(`/submissions/${submissionId}/evaluations`);
}

export function fetchAllEvaluations() {
  return apiRequest<EvaluationSummary[]>("/evaluations");
}

export function reEvaluateSubmission(submissionId: string) {
  return apiRequest<EvaluationDetail>(`/submissions/${submissionId}/re-evaluate`, {
    method: "POST",
    bodyJson: {},
  });
}

export function startBatchEvaluations(submissionIds: string[]) {
  return apiRequest<{ queued_count: number; already_running: boolean }>("/evaluations/batch/start", {
    method: "POST",
    bodyJson: { submission_ids: submissionIds },
  });
}

export function fetchBatchEvaluationStatus() {
  return apiRequest<BatchEvaluationStatus>("/evaluations/batch/status");
}

export function cancelBatchEvaluations() {
  return apiRequest<{ cancel_requested: boolean; was_active: boolean }>("/evaluations/batch/cancel", {
    method: "POST",
    bodyJson: {},
  });
}

export function fetchEvaluationDetail(evaluationId: string) {
  return apiRequest<EvaluationDetail>(`/evaluations/${evaluationId}`);
}

export function applyManualAdjustments(
  evaluationId: string,
  payload: { items: Array<{ criterion_score_id: string; manual_score: number | null; feedback: string | null }> },
) {
  return apiRequest<EvaluationDetail>(`/evaluations/${evaluationId}/manual-adjustments`, {
    method: "PATCH",
    bodyJson: payload,
  });
}
