import { apiRequest } from "@/lib/api-client";
import type { ProviderConfig, ProviderName, ProviderUsageSummary } from "@/types/api";

export function fetchProviders() {
  return apiRequest<ProviderConfig[]>("/providers");
}

export function createProvider(payload: {
  provider_name: ProviderName;
  api_key: string;
  model_name: string;
  is_active: boolean;
  is_default: boolean;
  daily_request_limit?: number;
  monthly_request_limit?: number;
  max_files_per_batch?: number;
  max_file_size_mb?: number;
  max_tokens_per_request?: number;
}) {
  return apiRequest<ProviderConfig>("/providers", {
    method: "POST",
    bodyJson: payload,
  });
}

export function updateProvider(
  providerId: string,
  payload: Partial<{
    api_key: string;
    model_name: string;
    is_active: boolean;
    is_default: boolean;
    daily_request_limit: number;
    monthly_request_limit: number;
    max_files_per_batch: number;
    max_file_size_mb: number;
    max_tokens_per_request: number;
  }>,
) {
  return apiRequest<ProviderConfig>(`/providers/${providerId}`, {
    method: "PATCH",
    bodyJson: payload,
  });
}

export function testProvider(providerId: string) {
  return apiRequest<{ success: boolean; message: string }>(`/providers/${providerId}/test`, {
    method: "POST",
  });
}

export function deleteProvider(providerId: string) {
  return apiRequest<void>(`/providers/${providerId}`, {
    method: "DELETE",
  });
}

export function fetchProviderUsage() {
  return apiRequest<ProviderUsageSummary[]>("/providers/usage");
}
