import { useAuthStore } from "@/app/store/use-auth-store";
import { usePreferenceStore } from "@/app/store/use-preference-store";
import { createApiRequestError } from "@/lib/error-messages";

// const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const API_BASE_URL = import.meta.env.VITE_API_URL;

type RequestOptions = RequestInit & {
  bodyJson?: unknown;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { accessToken, clearSession } = useAuthStore.getState();
  const { language } = usePreferenceStore.getState();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("Accept-Language", language === "ar" ? "ar" : "en");
  if (options.bodyJson !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      body: options.bodyJson !== undefined ? JSON.stringify(options.bodyJson) : options.body,
    });
  } catch (error) {
    throw createApiRequestError({
      code: "network_error",
      rawMessage: error instanceof Error ? error.message : "Failed to fetch",
    });
  }

  if (response.status === 401) {
    clearSession();
    throw createApiRequestError({
      code: "authentication_error",
      status: response.status,
      rawMessage: "Unauthorized",
    });
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | {
          error?: { code?: string; message?: string; details?: Record<string, unknown> };
          detail?: Array<{ msg?: string }> | { msg?: string } | string;
        }
      | null;
    const detailMessage = Array.isArray(payload?.detail)
      ? payload?.detail.map((item) => item.msg).filter(Boolean).join(", ")
      : typeof payload?.detail === "string"
        ? payload.detail
        : payload?.detail && typeof payload.detail === "object" && "msg" in payload.detail
          ? payload.detail.msg
          : undefined;
    throw createApiRequestError({
      code: payload?.error?.code,
      status: response.status,
      rawMessage: payload?.error?.message ?? detailMessage ?? "Request failed",
      details: payload?.error?.details,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
