import { PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { fetchProviders } from "@/services/providers";

function ProviderSetupGuard() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const providersQuery = useQuery({
    queryKey: ["providers"],
    queryFn: fetchProviders,
  });

  const hasDefaultProvider = providersQuery.data?.some((provider) => provider.is_active && provider.is_default);
  const shouldShow =
    !providersQuery.isPending &&
    location.pathname !== "/providers" &&
    providersQuery.data !== undefined &&
    !hasDefaultProvider;

  if (!shouldShow) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 p-4 backdrop-blur-md">
      <Card className="w-full max-w-md p-6 shadow-lift">
        <div className="mb-4 h-1.5 w-14 rounded-full bg-primary" />
        <h2 className="text-xl font-extrabold">{t("providers.guardTitle")}</h2>
        <p className="mt-3 text-sm leading-7 text-foreground/70">{t("providers.guardDescription")}</p>
        <div className="mt-5 flex gap-3">
          <Button className="flex-1" type="button" onClick={() => navigate("/providers")}>
            {t("providers.guardAction")}
          </Button>
        </div>
      </Card>
    </div>
  );
}

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen lg:flex">
      <Sidebar />
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <Topbar />
        <ProviderSetupGuard />
        <main className="mx-auto w-full max-w-[1540px] flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
