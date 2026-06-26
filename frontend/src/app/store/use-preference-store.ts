import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { LanguageCode, ThemeMode } from "@/types/api";

interface PreferenceState {
  language: LanguageCode;
  theme: ThemeMode;
  avatar: string | null;
  setLanguage: (language: LanguageCode) => void;
  setTheme: (theme: ThemeMode) => void;
  setAvatar: (avatar: string | null) => void;
}

export const usePreferenceStore = create<PreferenceState>()(
  persist(
    (set) => ({
      language: "ar",
      theme: "system",
      avatar: null,
      setLanguage: (language) => set({ language }),
      setTheme: (theme) => set({ theme }),
      setAvatar: (avatar) => set({ avatar }),
    }),
    {
      name: "mentis-preferences",
    },
  ),
);
