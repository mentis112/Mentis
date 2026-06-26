import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { InstructorProfile } from "@/types/api";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  instructor: InstructorProfile | null;
  setSession: (payload: {
    accessToken: string;
    refreshToken: string;
    instructor: InstructorProfile;
  }) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      instructor: null,
      setSession: ({ accessToken, refreshToken, instructor }) =>
        set({ accessToken, refreshToken, instructor }),
      clearSession: () =>
        set({ accessToken: null, refreshToken: null, instructor: null }),
    }),
    {
      name: "mentis-auth",
    },
  ),
);
