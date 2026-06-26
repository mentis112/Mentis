import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { Input } from "@/components/shared/input";
import { getUserFacingErrorMessage, getUserFacingReason } from "@/lib/error-messages";
import { Select } from "@/components/shared/select";
import {
  createProvider,
  deleteProvider,
  fetchProviderUsage,
  fetchProviders,
  testProvider,
  updateProvider,
} from "@/services/providers";
import type { ProviderConfig } from "@/types/api";

const optionalNumberField = (minimum: number) =>
  z.preprocess(
    (value) => {
      if (value === "" || value === null || value === undefined) {
        return undefined;
      }
      const parsed = Number(value);
      return Number.isNaN(parsed) ? value : parsed;
    },
    z.number().min(minimum).optional(),
  );

const schema = z.object({
  provider_name: z.enum(["openai", "gemini", "deepseek", "ollama", "groq"]),
  api_key: z.string().default(""),
  model_name: z.string().min(2),
  is_active: z.boolean().default(true),
  is_default: z.boolean().default(false),
  daily_request_limit: optionalNumberField(1),
  monthly_request_limit: optionalNumberField(1),
  max_files_per_batch: optionalNumberField(1),
  max_file_size_mb: optionalNumberField(1),
  max_tokens_per_request: optionalNumberField(256),
}).superRefine((values, ctx) => {
  if (values.provider_name !== "ollama" && values.api_key.trim().length < 8) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "providers.apiKeyValidation",
      path: ["api_key"],
    });
  }
});

type FormValues = z.infer<typeof schema>;

const providerDefaults: Record<
  FormValues["provider_name"],
  {
    model: string;
    hintKey: string;
    requiresApiKey: boolean;
    apiKeyHelpKey: string;
    apiKeyHelpUrl: string;
  }
> = {
  openai: {
    model: "gpt-4o-mini",
    hintKey: "providers.modelHintOpenAI",
    requiresApiKey: true,
    apiKeyHelpKey: "providers.apiKeyHelpOpenAI",
    apiKeyHelpUrl: "https://platform.openai.com/api-keys",
  },
  gemini: {
    model: "gemini-2.0-flash",
    hintKey: "providers.modelHintGemini",
    requiresApiKey: true,
    apiKeyHelpKey: "providers.apiKeyHelpGemini",
    apiKeyHelpUrl: "https://aistudio.google.com/app/apikey",
  },
  deepseek: {
    model: "deepseek-chat",
    hintKey: "providers.modelHintDeepSeek",
    requiresApiKey: true,
    apiKeyHelpKey: "providers.apiKeyHelpDeepSeek",
    apiKeyHelpUrl: "https://platform.deepseek.com/api_keys",
  },
  groq: {
    model: "llama-3.1-8b-instant",
    hintKey: "providers.modelHintGroq",
    requiresApiKey: true,
    apiKeyHelpKey: "providers.apiKeyHelpGroq",
    apiKeyHelpUrl: "https://console.groq.com/keys",
  },
  ollama: {
    model: "deepseek-r1:8b",
    hintKey: "providers.modelHintOllama",
    requiresApiKey: false,
    apiKeyHelpKey: "providers.apiKeyNotRequired",
    apiKeyHelpUrl: "",
  },
};

export function ProviderSettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const isEditing = Boolean(editingProviderId);
  const providersQuery = useQuery({ queryKey: ["providers"], queryFn: fetchProviders });
  const usageQuery = useQuery({ queryKey: ["provider-usage"], queryFn: fetchProviderUsage });
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      provider_name: "openai",
      model_name: "gpt-4o-mini",
      is_active: true,
      is_default: true,
    },
  });
  const providerName = form.watch("provider_name");

  const resetFormToCreateDefaults = () => {
    form.reset({
      provider_name: "openai",
      api_key: "",
      model_name: "gpt-4o-mini",
      is_active: true,
      is_default: true,
      daily_request_limit: undefined,
      monthly_request_limit: undefined,
      max_files_per_batch: undefined,
      max_file_size_mb: undefined,
      max_tokens_per_request: undefined,
    });
  };

  useEffect(() => {
    if (!isEditing) {
      form.setValue("model_name", providerDefaults[providerName].model, {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
    if (!providerDefaults[providerName].requiresApiKey) {
      form.setValue("api_key", "", { shouldDirty: true, shouldValidate: true });
    }
  }, [form, isEditing, providerName]);

  const createMutation = useMutation({
    mutationFn: createProvider,
    onSuccess: () => {
      resetFormToCreateDefaults();
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-usage"] });
      toast.success(t("common.create"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });
  const updateMutation = useMutation({
    mutationFn: ({ providerId, payload }: { providerId: string; payload: Parameters<typeof updateProvider>[1] }) =>
      updateProvider(providerId, payload),
    onSuccess: () => {
      setEditingProviderId(null);
      resetFormToCreateDefaults();
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-usage"] });
      toast.success(t("common.save"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const testMutation = useMutation({
    mutationFn: testProvider,
    onSuccess: (response) => {
      if (response.success) {
        toast.success(response.message);
        return;
      }
      toast.error(getUserFacingReason(response.message, "errors.provider.connectionFailed"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });
  const makeDefaultMutation = useMutation({
    mutationFn: (providerId: string) =>
      updateProvider(providerId, {
        is_default: true,
        is_active: true,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
      toast.success(t("providers.makeDefault"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });
  const deleteMutation = useMutation({
    mutationFn: (providerId: string) => deleteProvider(providerId),
    onSuccess: () => {
      if (editingProviderId) {
        setEditingProviderId(null);
        resetFormToCreateDefaults();
      }
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-usage"] });
      toast.success(t("common.delete"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const startEdit = (provider: ProviderConfig) => {
    setEditingProviderId(provider.id);
    form.reset({
      provider_name: provider.provider_name,
      api_key: "",
      model_name: provider.model_name,
      is_active: provider.is_active,
      is_default: provider.is_default,
      daily_request_limit: provider.daily_request_limit ?? undefined,
      monthly_request_limit: provider.monthly_request_limit ?? undefined,
      max_files_per_batch: provider.max_files_per_batch ?? undefined,
      max_file_size_mb: provider.max_file_size_mb ?? undefined,
      max_tokens_per_request: provider.max_tokens_per_request ?? undefined,
    });
  };

  const cancelEdit = () => {
    setEditingProviderId(null);
    resetFormToCreateDefaults();
  };

  const handleDelete = (provider: ProviderConfig) => {
    const confirmed = window.confirm(
      t("providers.deleteConfirm", {
        provider: provider.provider_name,
      }),
    );
    if (!confirmed) {
      return;
    }
    deleteMutation.mutate(provider.id);
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("providers.title")} subtitle={t("providers.subtitle")} />
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="p-5">
          <form
            className="grid gap-4"
            onSubmit={form.handleSubmit((values) => {
              const trimmedApiKey = values.api_key.trim();

              if (isEditing && editingProviderId) {
                const payload: Parameters<typeof updateProvider>[1] = {
                  model_name: values.model_name,
                  is_active: values.is_active,
                  is_default: values.is_default,
                  daily_request_limit: values.daily_request_limit,
                  monthly_request_limit: values.monthly_request_limit,
                  max_files_per_batch: values.max_files_per_batch,
                  max_file_size_mb: values.max_file_size_mb,
                  max_tokens_per_request: values.max_tokens_per_request,
                };

                if (trimmedApiKey) {
                  payload.api_key = trimmedApiKey;
                }

                updateMutation.mutate({ providerId: editingProviderId, payload });
                return;
              }

              createMutation.mutate({
                ...values,
                api_key: trimmedApiKey,
              });
            })}
          >
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("providers.provider")}</label>
              <Select {...form.register("provider_name")} disabled={isEditing}>
                <option value="openai">OpenAI</option>
                <option value="gemini">Gemini</option>
                <option value="deepseek">DeepSeek</option>
                <option value="groq">Groq</option>
                <option value="ollama">Ollama</option>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("providers.model")}</label>
              <Input {...form.register("model_name")} />
              <p className="text-xs text-foreground/60">{t(providerDefaults[providerName].hintKey)}</p>
            </div>
            {providerDefaults[providerName].requiresApiKey ? (
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("providers.apiKey")}</label>
                <Input {...form.register("api_key")} type="password" />
                <p className="text-xs text-foreground/60">
                  {t(providerDefaults[providerName].apiKeyHelpKey)}{" "}
                  <a
                    href={providerDefaults[providerName].apiKeyHelpUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-primary underline underline-offset-2"
                  >
                    {t("providers.apiKeyHelpLink")}
                  </a>
                </p>
                {form.formState.errors.api_key?.message ? (
                  <p className="text-xs text-destructive">
                    {t(form.formState.errors.api_key.message)}
                  </p>
                ) : null}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border bg-muted/60 p-4 text-sm text-foreground/70">
                {t("providers.apiKeyNotRequired")}
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("providers.dailyLimit")}</label>
                <Input {...form.register("daily_request_limit")} type="number" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("providers.monthlyLimit")}</label>
                <Input {...form.register("monthly_request_limit")} type="number" />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("providers.maxFiles")}</label>
                <Input {...form.register("max_files_per_batch")} type="number" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("providers.maxFileSize")}</label>
                <Input {...form.register("max_file_size_mb")} type="number" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("providers.maxTokens")}</label>
              <Input {...form.register("max_tokens_per_request")} type="number" />
            </div>
            <div className="flex gap-4">
              <label className="flex items-center gap-3 text-sm">
                <input {...form.register("is_active")} type="checkbox" className="size-4" />
                {t("groups.active")}
              </label>
              <label className="flex items-center gap-3 text-sm">
                <input {...form.register("is_default")} type="checkbox" className="size-4" />
                {t("providers.default")}
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {createMutation.isPending || updateMutation.isPending
                  ? t("common.loading")
                  : isEditing
                    ? t("common.save")
                    : t("common.create")}
              </Button>
              {isEditing ? (
                <Button type="button" variant="ghost" onClick={cancelEdit}>
                  {t("common.cancel")}
                </Button>
              ) : null}
            </div>
          </form>
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <h3 className="mb-4 text-lg font-semibold">{t("providers.usageSummary")}</h3>
            <div className="space-y-3">
              {usageQuery.data?.map((item) => (
                <div key={item.provider_name} className="rounded-2xl bg-muted/70 p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold capitalize">{item.provider_name}</p>
                    <Badge>{item.requests_this_month}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-foreground/70">
                    {t("dashboard.failuresBlocked", {
                      failures: item.failures_this_month,
                      blocked: item.blocked_this_month,
                    })}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          {providersQuery.data?.map((provider) => (
            <Card key={provider.id} className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-2">
                  <h3 className="font-semibold capitalize">{provider.provider_name}</h3>
                  <p className="text-sm text-foreground/70">{provider.model_name}</p>
                  <div className="flex flex-wrap gap-2">
                    {provider.is_default ? <Badge>{t("providers.default")}</Badge> : null}
                    {provider.is_active ? <Badge>{t("groups.active")}</Badge> : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {!provider.is_default ? (
                    <Button
                      variant="ghost"
                      type="button"
                      onClick={() => makeDefaultMutation.mutate(provider.id)}
                      disabled={makeDefaultMutation.isPending}
                    >
                      {t("providers.makeDefault")}
                    </Button>
                  ) : null}
                  <Button variant="secondary" type="button" onClick={() => testMutation.mutate(provider.id)}>
                    {t("providers.test")}
                  </Button>
                  <Button
                    variant="ghost"
                    type="button"
                    onClick={() => startEdit(provider)}
                    disabled={updateMutation.isPending}
                  >
                    {t("providers.edit")}
                  </Button>
                  <Button
                    variant="danger"
                    type="button"
                    onClick={() => handleDelete(provider)}
                    disabled={deleteMutation.isPending}
                  >
                    {t("common.delete")}
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
