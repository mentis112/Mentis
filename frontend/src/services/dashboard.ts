import { apiRequest } from "@/lib/api-client";
import type { DashboardSummary, ProviderUsageSummary } from "@/types/api";

export function fetchDashboardSummary() {
  return apiRequest<DashboardSummary>("/dashboard/summary");
}

export function fetchProviderUsageSummary() {
  return apiRequest<ProviderUsageSummary[]>("/providers/usage");
}

