import { Globe2, LogOut, MoonStar, SunMedium } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/shared/button";
import { useAuthStore } from "@/app/store/use-auth-store";
import { usePreferenceStore } from "@/app/store/use-preference-store";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import { navLinks } from "@/components/layout/nav-links";
import { cn } from "@/lib/cn";
import { logout } from "@/services/auth";

export function Topbar() {
  const { t } = useTranslation();
  const instructor = useAuthStore((state) => state.instructor);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearSession = useAuthStore((state) => state.clearSession);
  const { language, theme, avatar, setLanguage, setTheme } =
    usePreferenceStore();
  const displayName =
    instructor?.username?.trim() || instructor?.email?.split("@")[0] || "";
  const greeting = displayName
    ? language === "ar"
      ? `مرحباً، ${displayName}`
      : `Welcome, ${displayName}`
    : "";
  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (refreshToken) {
        await logout(refreshToken);
      }
    },
    onSettled: () => clearSession(),
    onSuccess: () => toast.success(t("nav.logout")),
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 px-4 py-3 backdrop-blur-xl sm:px-6 lg:px-8">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary/10 text-primary border border-primary/20 shadow-sm font-semibold">
            {avatar ? (
              <img
                src={avatar}
                alt="Profile"
                className="h-full w-full object-cover"
              />
            ) : (
              displayName.substring(0, 2).toUpperCase()
            )}
          </div>
          <div className="hidden sm:block min-w-0">
            <p className="truncate text-sm font-bold text-foreground">
              {language === "ar" ? "مرحباً يا" : "Welcome,"}{" "}
              <span className="text-primary">{displayName}</span> 👋
            </p>
            <p className="truncate text-xs text-foreground/60">
              {instructor?.email}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            onClick={() => setLanguage(language === "en" ? "ar" : "en")}
            type="button"
            className="h-10 px-3"
            title={t("common.language")}
          >
            <Globe2 size={16} />
            <span className="hidden sm:inline">
              {language === "en" ? t("common.arabic") : t("common.english")}
            </span>
          </Button>
          <Button
            variant="ghost"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            type="button"
            className="h-10 px-3"
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
          <Button
            variant="secondary"
            onClick={() => logoutMutation.mutate()}
            type="button"
            className="h-10 px-3"
          >
            <LogOut size={16} />
            <span className="hidden sm:inline">{t("nav.logout")}</span>
          </Button>
        </div>
      </div>
      <nav className="mt-3 flex gap-2 overflow-x-auto pb-1 lg:hidden">
        {navLinks.map(({ to, icon: Icon, key }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "inline-flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold transition",
                isActive
                  ? "border-primary/25 bg-primary/10 text-primary"
                  : "border-border/65 bg-card/65 text-foreground/65",
              )
            }
          >
            <Icon size={15} />
            {t(key)}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
