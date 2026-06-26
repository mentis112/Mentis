import type { AuthResponse } from "@/types/api";
import { apiRequest } from "@/lib/api-client";

export function login(payload: { email: string; password: string }) {
  return apiRequest<AuthResponse>("/auth/login", {
    method: "POST",
    bodyJson: payload,
  });
}

export function register(payload: { username: string; email: string; password: string }) {
  return apiRequest<AuthResponse>("/auth/register", {
    method: "POST",
    bodyJson: payload,
  });
}

export function logout(refreshToken: string) {
  return apiRequest<{ message: string }>("/auth/logout", {
    method: "POST",
    bodyJson: { refresh_token: refreshToken },
  });
}

export function changePassword(payload: { current_password: string; new_password: string }) {
  return apiRequest<{ message: string }>("/auth/change-password", {
    method: "POST",
    bodyJson: payload,
  });
}
