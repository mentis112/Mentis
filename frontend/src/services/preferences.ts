import { apiRequest } from "@/lib/api-client";
import type { Preference } from "@/types/api";

export function fetchPreferences() {
  return apiRequest<Preference>("/preferences");
}

export function updatePreferences(payload: { language: "en" | "ar"; theme: "light" | "dark" | "system" }) {
  return apiRequest<Preference>("/preferences", {
    method: "PATCH",
    bodyJson: payload,
  });
}

