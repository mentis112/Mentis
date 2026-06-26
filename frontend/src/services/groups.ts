import { apiRequest } from "@/lib/api-client";
import type { AssignmentGroup, EvaluationCriterion } from "@/types/api";

export function fetchGroups() {
  return apiRequest<AssignmentGroup[]>("/groups");
}

export function fetchGroup(groupId: string) {
  return apiRequest<AssignmentGroup>(`/groups/${groupId}`);
}

export function createGroup(payload: {
  name: string;
  description?: string;
  grade_scale: number;
  is_active: boolean;
}) {
  return apiRequest<AssignmentGroup>("/groups", {
    method: "POST",
    bodyJson: payload,
  });
}

export function updateGroup(
  groupId: string,
  payload: Partial<{
    name: string;
    description?: string | null;
    grade_scale: number;
    is_active: boolean;
  }>,
) {
  return apiRequest<AssignmentGroup>(`/groups/${groupId}`, {
    method: "PATCH",
    bodyJson: payload,
  });
}

export function createCriterion(
  groupId: string,
  payload: {
    name: string;
    weight: number;
    description?: string;
    is_manual: boolean;
    sort_order: number;
  },
) {
  return apiRequest<EvaluationCriterion>(`/groups/${groupId}/criteria`, {
    method: "POST",
    bodyJson: payload,
  });
}

export function updateCriterion(
  criterionId: string,
  payload: Partial<{
    name: string;
    weight: number;
    description?: string;
    is_manual: boolean;
    sort_order: number;
  }>,
) {
  return apiRequest<EvaluationCriterion>(`/criteria/${criterionId}`, {
    method: "PATCH",
    bodyJson: payload,
  });
}

export function deleteCriterion(criterionId: string) {
  return apiRequest<void>(`/criteria/${criterionId}`, {
    method: "DELETE",
  });
}

export function deleteGroup(groupId: string) {
  return apiRequest<void>(`/groups/${groupId}`, {
    method: "DELETE",
  });
}
