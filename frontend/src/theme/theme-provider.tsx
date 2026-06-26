import { PropsWithChildren, useEffect } from "react";

import { usePreferenceStore } from "@/app/store/use-preference-store";

export function ThemeProvider({ children }: PropsWithChildren) {
  const theme = usePreferenceStore((state) => state.theme);

  useEffect(() => {
    const root = document.documentElement;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const resolvedTheme = theme === "system" ? (mediaQuery.matches ? "dark" : "light") : theme;
      root.classList.toggle("dark", resolvedTheme === "dark");
      root.dataset.theme = resolvedTheme;
    };
    applyTheme();

    if (theme !== "system") {
      return;
    }

    mediaQuery.addEventListener("change", applyTheme);
    return () => mediaQuery.removeEventListener("change", applyTheme);
  }, [theme]);

  return <>{children}</>;
}
