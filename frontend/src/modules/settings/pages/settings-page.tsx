import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useRef } from "react";
import { z } from "zod";
import {
  User,
  Mail,
  Shield,
  Pencil,
  Camera,
  Globe,
  Palette,
  Sun,
  Moon,
  Monitor,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { useAuthStore } from "@/app/store/use-auth-store";
import { usePreferenceStore } from "@/app/store/use-preference-store";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { Input } from "@/components/shared/input";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import { Select } from "@/components/shared/select";
import { changePassword } from "@/services/auth";
import { fetchPreferences, updatePreferences } from "@/services/preferences";

const passwordSchema = z
  .object({
    current_password: z.string().min(8),
    new_password: z.string().min(8),
    confirm_password: z.string().min(8),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "settings.passwordMismatch",
  });

type PasswordFormValues = z.infer<typeof passwordSchema>;

export function SettingsPage() {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const instructor = useAuthStore((state) => state.instructor);
  const { language, theme, avatar, setLanguage, setTheme, setAvatar } =
    usePreferenceStore();
  const passwordForm = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });
  useQuery({
    queryKey: ["preferences"],
    queryFn: fetchPreferences,
  });
  const mutation = useMutation({
    mutationFn: updatePreferences,
    onSuccess: () => toast.success(t("settings.sync")),
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });
  const passwordMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      passwordForm.reset();
      toast.success(t("settings.passwordChanged"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const handleAvatarChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        toast.error(
          t(
            "settings.avatarSizeError",
            "Profile picture must be 5 MB or smaller",
          ),
        );
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatar(reader.result as string);
        toast.success(
          t("settings.avatarUpdated", "Profile picture updated successfully"),
        );
      };
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("settings.title")}
        subtitle={t("settings.subtitle")}
      />
      <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <Card className="flex flex-col items-center p-6 text-center">
          <div className="relative mb-4 mt-2">
            <div className="flex h-24 w-24 overflow-hidden items-center justify-center rounded-full bg-primary text-3xl font-bold text-primary-foreground shadow-sm">
              {avatar ? (
                <img
                  src={avatar}
                  alt="Avatar"
                  className="h-full w-full object-cover"
                />
              ) : (
                instructor?.username?.substring(0, 2).toUpperCase()
              )}
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleAvatarChange}
              className="hidden"
              accept="image/*"
            />
            <button
              title={t("settings.editProfile")}
              onClick={() => fileInputRef.current?.click()}
              className="absolute bottom-0 end-0 flex h-7 w-7 items-center justify-center rounded-full border-2 border-background bg-muted text-foreground transition-colors hover:bg-muted-foreground/20"
            >
              <Camera className="h-3.5 w-3.5" />
            </button>
          </div>
          <h2 className="text-xl font-bold">{instructor?.username}</h2>
          <p className="text-sm text-foreground/60 mb-6">{instructor?.email}</p>

          <div className="w-full space-y-4 rounded-xl border border-muted-foreground/10 bg-muted/20 p-4 mb-6">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 text-foreground/70">
                <User className="h-4 w-4" />
                <span>{t("settings.username")}</span>
              </div>
              <span className="font-medium">{instructor?.username}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 text-foreground/70">
                <Mail className="h-4 w-4" />
                <span>{t("settings.email")}</span>
              </div>
              <span className="font-medium">{instructor?.email}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 text-foreground/70">
                <Shield className="h-4 w-4" />
                <span>{t("settings.role")}</span>
              </div>
              <span className="font-medium text-primary">
                {t("settings.admin")}
              </span>
            </div>
          </div>

          <div className="mt-4 w-full relative overflow-hidden rounded-xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border border-primary/20 p-5 text-start transition-all hover:border-primary/30">
            <div className="relative z-10 flex items-start gap-3">
              <div className="rounded-full bg-primary/20 p-2 text-primary">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-semibold text-sm mb-1">
                  {t("settings.accountVerified", "Verified and secure account")}
                </h4>
                <p className="text-xs text-foreground/70 leading-relaxed font-medium">
                  {t(
                    "settings.accountVerifiedDesc",
                    "This account has full instructor permissions and is protected with modern security and encryption standards to keep your data safe.",
                  )}
                </p>
              </div>
            </div>

            <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-primary/10 blur-2xl"></div>
            <div className="absolute -left-6 -bottom-6 h-24 w-24 rounded-full bg-primary/10 blur-2xl"></div>
          </div>
        </Card>
        <div className="space-y-6">
          <Card className="p-6">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Monitor className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold">
                {t("settings.preferences")}
              </h3>
            </div>

            <div className="grid gap-6 md:grid-cols-2 mb-8">
              <div className="space-y-4">
                <label className="flex items-center gap-2 text-sm font-semibold">
                  <Globe className="h-4 w-4 text-primary" />
                  <span>{t("common.language")}</span>
                </label>
                <Select
                  value={language}
                  onChange={(event) =>
                    setLanguage(event.target.value as "en" | "ar")
                  }
                  className="rounded-xl h-12"
                >
                  <option value="en">{t("common.english")}</option>
                  <option value="ar">{t("common.arabic")}</option>
                </Select>
              </div>

              <div className="space-y-4">
                <label className="flex items-center gap-2 text-sm font-semibold">
                  <Palette className="h-4 w-4 text-primary" />
                  <span>{t("common.theme")}</span>
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setTheme("system")}
                    className={`flex flex-1 flex-col items-center justify-center gap-2 rounded-xl py-3 outline-none transition-all ${
                      theme === "system"
                        ? "bg-primary/5 text-primary border-2 border-primary font-medium"
                        : "text-muted-foreground hover:bg-muted border border-border"
                    }`}
                  >
                    <Monitor className="h-5 w-5" />
                    <span className="text-xs">{t("common.system")}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setTheme("dark")}
                    className={`flex flex-1 flex-col items-center justify-center gap-2 rounded-xl py-3 outline-none transition-all ${
                      theme === "dark"
                        ? "bg-primary/5 text-primary border-2 border-primary font-medium"
                        : "text-muted-foreground hover:bg-muted border border-border"
                    }`}
                  >
                    <Moon className="h-5 w-5" />
                    <span className="text-xs">{t("common.dark")}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setTheme("light")}
                    className={`flex flex-1 flex-col items-center justify-center gap-2 rounded-xl py-3 outline-none transition-all ${
                      theme === "light"
                        ? "bg-primary/5 text-primary border-2 border-primary font-medium"
                        : "text-muted-foreground hover:bg-muted border border-border"
                    }`}
                  >
                    <Sun className="h-5 w-5" />
                    <span className="text-xs">{t("common.light")}</span>
                  </button>
                </div>
              </div>
            </div>

            <Button
              className="gap-2 rounded-xl text-primary font-semibold"
              variant="secondary"
              onClick={() => mutation.mutate({ language, theme })}
              type="button"
              disabled={mutation.isPending}
            >
              <RefreshCw
                className={`h-4 w-4 ${mutation.isPending ? "animate-spin" : ""}`}
              />
              {mutation.isPending ? t("common.loading") : t("settings.sync")}
            </Button>
          </Card>

          <Card className="p-5">
            <h3 className="mb-4 text-lg font-semibold">
              {t("settings.changePassword")}
            </h3>
            <form
              className="space-y-4"
              onSubmit={passwordForm.handleSubmit((values) =>
                passwordMutation.mutate({
                  current_password: values.current_password,
                  new_password: values.new_password,
                }),
              )}
            >
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t("settings.currentPassword")}
                </label>
                <Input
                  {...passwordForm.register("current_password")}
                  type="password"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t("settings.newPassword")}
                </label>
                <Input
                  {...passwordForm.register("new_password")}
                  type="password"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t("settings.confirmPassword")}
                </label>
                <Input
                  {...passwordForm.register("confirm_password")}
                  type="password"
                />
                {passwordForm.formState.errors.confirm_password?.message ? (
                  <p className="text-xs text-destructive">
                    {t(passwordForm.formState.errors.confirm_password.message)}
                  </p>
                ) : null}
              </div>
              <Button type="submit" disabled={passwordMutation.isPending}>
                {passwordMutation.isPending
                  ? t("common.loading")
                  : t("common.save")}
              </Button>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}
