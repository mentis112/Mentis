import { PropsWithChildren, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { ThemeProvider } from "@/theme/theme-provider";
import { usePreferenceStore } from "@/app/store/use-preference-store";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function LocaleSynchronizer() {
  const language = usePreferenceStore((state) => state.language);
  const { i18n } = useTranslation();

  useEffect(() => {
    void i18n.changeLanguage(language);
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  }, [i18n, language]);

  return null;
}

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <LocaleSynchronizer />
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}

