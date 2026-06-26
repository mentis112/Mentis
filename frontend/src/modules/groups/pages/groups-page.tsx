import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/shared/input";
import { Textarea } from "@/components/shared/textarea";
import { Badge } from "@/components/shared/badge";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import {
  createCriterion,
  createGroup,
  deleteGroup,
  fetchGroups,
} from "@/services/groups";
import type { AssignmentGroup } from "@/types/api";

const optionalWeightField = z.preprocess((value) => {
  if (value === "" || value === null || value === undefined) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? value : parsed;
}, z.number().positive().max(100).optional());

const criterionDraftSchema = z.object({
  name: z.string().default(""),
  weight: optionalWeightField,
  description: z.string().default(""),
  is_manual: z.boolean().default(false),
});

const schema = z
  .object({
    name: z.string().min(2),
    description: z.string().optional(),
    grade_scale: z.coerce.number().min(1),
    is_active: z.boolean().default(true),
    criteria: z.array(criterionDraftSchema).default([]),
  })
  .superRefine((values, ctx) => {
    const activeCriteria = values.criteria
      .map((criterion, index) => ({ ...criterion, index }))
      .filter(
        (criterion) =>
          criterion.name.trim() ||
          criterion.description.trim() ||
          criterion.weight !== undefined ||
          criterion.is_manual,
      );

    if (!activeCriteria.length) {
      return;
    }

    let total = 0;
    for (const criterion of activeCriteria) {
      if (criterion.name.trim().length < 2) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "groups.criterionNameValidation",
          path: ["criteria", criterion.index, "name"],
        });
      }
      if (criterion.weight === undefined) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "groups.weightValidation",
          path: ["criteria", criterion.index, "weight"],
        });
        continue;
      }
      total += criterion.weight;
    }

    if (Math.round(total * 100) / 100 !== 100) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "groups.weightTotalValidation",
        path: ["criteria"],
      });
    }
  });

type FormValues = z.infer<typeof schema>;
type CriterionDraft = FormValues["criteria"][number];

const blankCriterion = (): CriterionDraft => ({
  name: "",
  weight: undefined,
  description: "",
  is_manual: false,
});

const hasCriterionContent = (criterion: CriterionDraft) =>
  Boolean(
    criterion.name.trim() ||
    criterion.description.trim() ||
    criterion.weight !== undefined ||
    criterion.is_manual,
  );

export function GroupsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [groupPendingDelete, setGroupPendingDelete] =
    useState<AssignmentGroup | null>(null);
  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
  });

  const totalGroups = groupsQuery.data?.length ?? 0;
  const paginatedGroups = useMemo(() => {
    if (!groupsQuery.data) return [];

    // Ensure the current page is valid when deleting items
    const maxPage = Math.max(1, Math.ceil(totalGroups / pageSize));
    if (page > maxPage) {
      setPage(maxPage);
    }

    const start = (page - 1) * pageSize;
    return groupsQuery.data.slice(start, start + pageSize);
  }, [groupsQuery.data, page, pageSize, totalGroups]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      is_active: true,
      grade_scale: 100,
      criteria: [blankCriterion()],
    },
  });
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "criteria",
  });
  const criteriaValues = form.watch("criteria");
  const activeCriteriaCount = useMemo(
    () => criteriaValues.filter(hasCriterionContent).length,
    [criteriaValues],
  );
  const criteriaTotal = useMemo(
    () =>
      Math.round(
        criteriaValues.reduce(
          (sum, criterion) => sum + Number(criterion.weight ?? 0),
          0,
        ) * 100,
      ) / 100,
    [criteriaValues],
  );
  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const group = await createGroup({
        name: values.name,
        description: values.description,
        grade_scale: values.grade_scale,
        is_active: values.is_active,
      });
      const criteria = values.criteria
        .filter(hasCriterionContent)
        .map((criterion, index) => ({
          name: criterion.name.trim(),
          weight: Number(criterion.weight),
          description: criterion.description.trim() || undefined,
          is_manual: criterion.is_manual,
          sort_order: index,
        }));

      let createdCriteria = 0;
      try {
        for (const criterion of criteria) {
          await createCriterion(group.id, criterion);
          createdCriteria += 1;
        }
      } catch (error) {
        const message =
          error instanceof Error && error.message
            ? error.message
            : t("common.retry");
        throw new Error(
          t("groups.criteriaCreatePartial", {
            count: createdCriteria,
            message,
          }),
        );
      }

      return { createdCriteria };
    },
    onSuccess: ({ createdCriteria }) => {
      form.reset({
        name: "",
        description: "",
        grade_scale: 100,
        is_active: true,
        criteria: [blankCriterion()],
      });
      toast.success(
        createdCriteria
          ? t("groups.createWithCriteriaSuccess", { count: createdCriteria })
          : t("common.create"),
      );
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteGroup,
    onSuccess: (_, deletedGroupId) => {
      setGroupPendingDelete(null);
      queryClient.setQueryData(
        ["groups"],
        (currentGroups: Awaited<ReturnType<typeof fetchGroups>> | undefined) =>
          currentGroups?.filter((group) => group.id !== deletedGroupId) ??
          currentGroups,
      );
      toast.success(t("groups.deleteSuccess"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["submissions"] });
      void queryClient.invalidateQueries({ queryKey: ["submission-report"] });
      void queryClient.invalidateQueries({ queryKey: ["all-evaluations"] });
    },
  });

  const handleDeleteGroup = (group: AssignmentGroup) => {
    setGroupPendingDelete(group);
  };

  const confirmDeleteGroup = () => {
    if (!groupPendingDelete) {
      return;
    }
    deleteMutation.mutate(groupPendingDelete.id);
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("groups.title")} subtitle={t("groups.subtitle")} />
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="p-5">
          <h3 className="mb-4 text-lg font-semibold">{t("common.create")}</h3>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          >
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.name")}</label>
              <Input {...form.register("name")} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("groups.description")}
              </label>
              <Textarea {...form.register("description")} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("groups.gradeScale")}
              </label>
              <Input {...form.register("grade_scale")} type="number" />
            </div>
            <div className="space-y-4 rounded-2xl border border-border/70 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h4 className="text-sm font-semibold">
                    {t("groups.criteriaCreateTitle")}
                  </h4>
                  <p className="text-xs text-foreground/60">
                    {t("groups.criteriaCreateHint")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge>{`${t("groups.criteriaCount")}: ${activeCriteriaCount}`}</Badge>
                  <Badge
                    className={
                      criteriaTotal === 100
                        ? "bg-emerald-100 text-emerald-700"
                        : ""
                    }
                  >
                    {`${t("groups.weights")}: ${criteriaTotal}`}
                  </Badge>
                </div>
              </div>

              <div className="space-y-3">
                {fields.map((field, index) => (
                  <div key={field.id} className="rounded-2xl bg-muted/60 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-sm font-semibold">
                        {t("groups.criteriaItem", { index: index + 1 })}
                      </p>
                      <Button
                        variant="ghost"
                        type="button"
                        onClick={() => remove(index)}
                        disabled={fields.length === 1}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-[1.2fr_0.8fr]">
                      <div className="space-y-2">
                        <label className="text-sm font-medium">
                          {t("groups.criterionName")}
                        </label>
                        <Input {...form.register(`criteria.${index}.name`)} />
                        {form.formState.errors.criteria?.[index]?.name
                          ?.message ? (
                          <p className="text-xs text-destructive">
                            {t(
                              form.formState.errors.criteria[index]?.name
                                ?.message as string,
                            )}
                          </p>
                        ) : null}
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium">
                          {t("groups.weight")}
                        </label>
                        <Input
                          {...form.register(`criteria.${index}.weight`)}
                          type="number"
                          step="0.01"
                        />
                        {form.formState.errors.criteria?.[index]?.weight
                          ?.message ? (
                          <p className="text-xs text-destructive">
                            {t(
                              form.formState.errors.criteria[index]?.weight
                                ?.message as string,
                            )}
                          </p>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-4 space-y-2">
                      <label className="text-sm font-medium">
                        {t("groups.description")}
                      </label>
                      <Textarea
                        {...form.register(`criteria.${index}.description`)}
                        className="min-h-20"
                      />
                    </div>

                    <label className="mt-4 flex items-center gap-3 text-sm">
                      <input
                        {...form.register(`criteria.${index}.is_manual`)}
                        type="checkbox"
                        className="size-4"
                      />
                      {t("groups.manual")}
                    </label>
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => append(blankCriterion())}
                  className="w-full"
                >
                  <span className="inline-flex items-center gap-2">
                    <Plus size={16} />
                    {t("groups.addCriterion")}
                  </span>
                </Button>
                {Array.isArray(form.formState.errors.criteria) ? null : form
                    .formState.errors.criteria?.message ? (
                  <p className="text-xs text-destructive">
                    {t(form.formState.errors.criteria.message as string)}
                  </p>
                ) : null}
              </div>
            </div>
            <label className="flex items-center gap-3 text-sm">
              <input
                {...form.register("is_active")}
                type="checkbox"
                className="size-4"
              />
              {t("groups.active")}
            </label>
            <Button
              className="w-full"
              disabled={mutation.isPending}
              type="submit"
            >
              {mutation.isPending ? t("common.loading") : t("common.create")}
            </Button>
          </form>
        </Card>

        <div className="space-y-4">
          {paginatedGroups.length ? (
            paginatedGroups.map((group) => (
              <Card key={group.id} className="p-5">
                <div className="flex flex-col gap-4">
                  <div className="space-y-2">
                    <h3 className="text-lg font-semibold">{group.name}</h3>
                    <p className="text-sm text-foreground/70">
                      {group.description}
                    </p>
                  </div>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex flex-wrap gap-2">
                      <Badge>{`${t("groups.gradeScale")}: ${group.grade_scale}`}</Badge>
                      <Badge>{`${t("groups.criteriaCount")}: ${group.criteria?.length ?? 0}`}</Badge>
                      <Badge>{`${t("groups.weights")}: ${group.weights_total ?? 0}`}</Badge>
                      <Badge
                        className={
                          group.ready_for_evaluation
                            ? "bg-emerald-100 text-emerald-700"
                            : ""
                        }
                      >
                        {group.ready_for_evaluation
                          ? t("state.completed")
                          : t("state.pending")}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-2 lg:shrink-0">
                      <Link to={`/groups/${group.id}`}>
                        <Button
                          variant="secondary"
                          className="min-w-28 whitespace-nowrap"
                        >
                          {t("groups.details")}
                        </Button>
                      </Link>
                      <Button
                        variant="danger"
                        type="button"
                        className="min-w-28 whitespace-nowrap"
                        onClick={() => handleDeleteGroup(group)}
                        disabled={
                          deleteMutation.isPending &&
                          deleteMutation.variables === group.id
                        }
                      >
                        {deleteMutation.isPending &&
                        deleteMutation.variables === group.id
                          ? t("common.loading")
                          : t("groups.delete")}
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            ))
          ) : (
            <EmptyState
              title={t("groups.title")}
              description={t("groups.empty")}
            />
          )}

          {totalGroups > 0 && (
            <PaginationControls
              page={page}
              pageSize={pageSize}
              total={totalGroups}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          )}
        </div>
      </div>

      {groupPendingDelete ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-lg p-6 shadow-2xl">
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">
                  {t("groups.deleteDialogTitle")}
                </h3>
                <p className="text-sm leading-7 text-foreground/75">
                  {t("groups.deleteConfirm", {
                    name: groupPendingDelete.name,
                    criteriaCount: groupPendingDelete.criteria?.length ?? 0,
                    submissionsCount: groupPendingDelete.submissions_count ?? 0,
                  })}
                </p>
              </div>
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <Button
                  variant="ghost"
                  type="button"
                  className="sm:min-w-28"
                  onClick={() => setGroupPendingDelete(null)}
                  disabled={deleteMutation.isPending}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  variant="danger"
                  type="button"
                  className="sm:min-w-32"
                  onClick={confirmDeleteGroup}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending
                    ? t("common.loading")
                    : t("groups.delete")}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
