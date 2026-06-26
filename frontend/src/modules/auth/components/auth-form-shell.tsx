import { PropsWithChildren } from "react";
import {
  Globe2,
  MoonStar,
  ShieldCheck,
  Sparkles,
  SunMedium,
  BrainCircuit,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { usePreferenceStore } from "@/app/store/use-preference-store";

export function AuthFormShell({
  title,
  subtitle,
  children,
}: PropsWithChildren<{ title: string; subtitle: string }>) {
  const { t } = useTranslation();
  const { language, theme, setLanguage, setTheme } = usePreferenceStore();

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
      <div className="absolute inset-x-0 top-0 h-1 bg-primary/70" />
      <Card className="grid w-full max-w-6xl overflow-hidden lg:grid-cols-[1.04fr_0.96fr]">
        <div className="relative hidden min-h-[650px] overflow-hidden border-e border-border/60 bg-surface/70 p-10 lg:block">
          <div className="relative z-10 flex h-full flex-col justify-between">
            <div className="max-w-md space-y-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-white shadow-glow dark:text-slate-950">
                <BrainCircuit size={28} />
              </div>
              <div>
                <p className="text-xs font-bold uppercase text-foreground/45">
                  Mentis
                </p>
                <h1 className="mt-3 text-4xl font-extrabold leading-tight">
                  {t("app.name")}
                </h1>
              </div>
              <p className="text-sm leading-7 text-foreground/70">{title}</p>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                {[
                  ["98%", t("dashboard.completed")],
                  ["24/7", t("dashboard.providerUsage")],
                  ["2", t("common.language")],
                ].map(([value, label]) => (
                  <div
                    key={label}
                    className="rounded-2xl border border-border/70 bg-card/70 p-4 shadow-sm"
                  >
                    <p className="text-2xl font-extrabold text-primary">
                      {value}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-foreground/55">
                      {label}
                    </p>
                  </div>
                ))}
              </div>
              <div className="rounded-2xl border border-border/70 bg-card/70 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <span className="inline-flex items-center gap-2 text-sm font-bold">
                    <ShieldCheck size={17} className="text-primary" />
                    {t("app.name")}
                  </span>
                  <span className="rounded-full bg-success/10 px-2.5 py-1 text-xs font-bold text-success">
                    {t("state.completed")}
                  </span>
                </div>
                <div className="space-y-2">
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 w-[86%] rounded-full bg-primary" />
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 w-[64%] rounded-full bg-accent" />
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 w-[42%] rounded-full bg-info" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex min-h-[650px] flex-col p-5 sm:p-8 lg:p-10">
          <div className="mb-8 flex items-center justify-between gap-3">
            <div className="lg:hidden">
              <p className="text-xs font-bold uppercase text-foreground/45">
                Mentis
              </p>
              <p className="mt-1 text-sm font-extrabold">{t("app.name")}</p>
            </div>
            <div className="ms-auto flex items-center gap-2">
              <Button
                variant="ghost"
                type="button"
                className="h-10 px-3"
                onClick={() => setLanguage(language === "en" ? "ar" : "en")}
                title={t("common.language")}
              >
                <Globe2 size={16} />
                <span className="hidden sm:inline">
                  {language === "en" ? t("common.arabic") : t("common.english")}
                </span>
              </Button>
              <Button
                variant="ghost"
                type="button"
                className="h-10 px-3"
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                title={t("common.theme")}
              >
                {theme === "dark" ? (
                  <SunMedium size={16} />
                ) : (
                  <MoonStar size={16} />
                )}
                <span className="hidden sm:inline">
                  {theme === "dark" ? t("common.light") : t("common.dark")}
                </span>
              </Button>
            </div>
          </div>

          <div className="m-auto w-full max-w-md">
            <div className="mb-7 space-y-2">
              <div className="h-1.5 w-12 rounded-full bg-primary" />
              <h2 className="text-2xl font-extrabold sm:text-3xl">{title}</h2>
              <p className="text-sm leading-7 text-foreground/65">{subtitle}</p>
            </div>
            {children}
          </div>
        </div>
      </Card>
    </div>
  );
}
