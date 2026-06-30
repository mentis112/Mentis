import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Eye, Pencil, Plus, Trash2, X } from "lucide-react";
import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/shared/input";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { Textarea } from "@/components/shared/textarea";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import {
  createCriterion,
  createGroup,
  deleteCriterion,
  deleteGroup,
  fetchGroups,
  updateCriterion,
  updateGroup,
} from "@/services/groups";
import type { AssignmentGroup } from "@/types/api";

const optionalWeightField = z.preprocess((value) => {
  if (value === "" || value === null || value === undefined) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? value : parsed;
}, z.number().positive().max(1000).optional());

const criterionDraftSchema = z.object({
  criterion_id: z.string().optional(),
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
    enable_auto_score_adjustment: z.boolean().default(true),
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
      }
    }
  });

type FormValues = z.infer<typeof schema>;
type CriterionDraft = FormValues["criteria"][number];

const blankCriterion = (): CriterionDraft => ({
  criterion_id: undefined,
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

const toFormValues = (group: AssignmentGroup): FormValues => ({
  name: group.name,
  description: group.description ?? "",
  grade_scale: group.grade_scale,
  enable_auto_score_adjustment: group.enable_auto_score_adjustment,
  is_active: group.is_active,
  criteria:
    group.criteria?.length
      ? [...group.criteria]
          .sort((left, right) => left.sort_order - right.sort_order)
          .map((criterion) => ({
            criterion_id: criterion.id,
            name: criterion.name,
            weight: criterion.weight,
            description: criterion.description ?? "",
            is_manual: criterion.is_manual,
          }))
      : [blankCriterion()],
});

const blankFormValues = (): FormValues => ({
  name: "",
  description: "",
  grade_scale: 100,
  enable_auto_score_adjustment: true,
  is_active: true,
  criteria: [blankCriterion()],
});

export function GroupsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [editingGroup, setEditingGroup] = useState<AssignmentGroup | null>(null);
  const [pendingEditValues, setPendingEditValues] = useState<FormValues | null>(null);
  const [groupPendingDelete, setGroupPendingDelete] = useState<AssignmentGroup | null>(null);
  const [showWeightError, setShowWeightError] = useState(false);
  const [groupsListHeight, setGroupsListHeight] = useState<number | null>(null);
  const formCardRef = useRef<HTMLDivElement | null>(null);

  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: blankFormValues(),
  });
  const { fields, append, remove, replace } = useFieldArray({
    control: form.control,
    name: "criteria",
  });

  const criteriaValues = form.watch("criteria");
  const gradeScale = form.watch("grade_scale");
  const activeCriteria = criteriaValues.filter(hasCriterionContent);
  const activeCriteriaCount = activeCriteria.length;
  const criteriaTotal =
    Math.round(
      activeCriteria.reduce((sum, criterion) => sum + (Number(criterion.weight) || 0), 0) * 100,
    ) / 100;
  const isWeightValid =
    activeCriteriaCount > 0 && Math.round(criteriaTotal * 100) / 100 === Number(gradeScale);

  const totalGroups = groupsQuery.data?.length ?? 0;
  const paginatedGroups = useMemo(() => {
    if (!groupsQuery.data) return [];

    const maxPage = Math.max(1, Math.ceil(totalGroups / pageSize));
    if (page > maxPage) {
      setPage(maxPage);
    }

    const start = (page - 1) * pageSize;
    return groupsQuery.data.slice(start, start + pageSize);
  }, [groupsQuery.data, page, pageSize, totalGroups]);

  useEffect(() => {
    const state = location.state as { editGroupId?: string } | null;
    if (!state?.editGroupId || !groupsQuery.data?.length) {
      return;
    }
    const group = groupsQuery.data.find((item) => item.id === state.editGroupId);
    if (group) {
      beginEditGroup(group);
      navigate(location.pathname, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupsQuery.data, location.pathname, location.state, navigate]);

  useEffect(() => {
    const element = formCardRef.current;
    if (!element) {
      return;
    }

    const updateGroupsListHeight = () => {
      setGroupsListHeight(Math.ceil(element.getBoundingClientRect().height));
    };

    updateGroupsListHeight();
    window.addEventListener("resize", updateGroupsListHeight);

    if (typeof ResizeObserver === "undefined") {
      return () => window.removeEventListener("resize", updateGroupsListHeight);
    }

    const resizeObserver = new ResizeObserver(updateGroupsListHeight);
    resizeObserver.observe(element);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateGroupsListHeight);
    };
  }, []);

  const resetToCreateMode = () => {
    setEditingGroup(null);
    setPendingEditValues(null);
    setShowWeightError(false);
    form.reset(blankFormValues());
    replace([blankCriterion()]);
  };

  function beginEditGroup(group: AssignmentGroup) {
    setEditingGroup(group);
    setPendingEditValues(null);
    setShowWeightError(false);
    const values = toFormValues(group);
    form.reset(values);
    replace(values.criteria);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const invalidateGroupData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["submissions"] }),
      queryClient.invalidateQueries({ queryKey: ["submission-report"] }),
      queryClient.invalidateQueries({ queryKey: ["all-evaluations"] }),
    ]);
  };

  const createMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const group = await createGroup({
        name: values.name.trim(),
        description: values.description?.trim() || undefined,
        grade_scale: Number(values.grade_scale),
        enable_auto_score_adjustment: values.enable_auto_score_adjustment,
        is_active: values.is_active,
      });
      const criteria = values.criteria.filter(hasCriterionContent);
      let createdCriteria = 0;
      try {
        for (const [index, criterion] of criteria.entries()) {
          await createCriterion(group.id, {
            name: criterion.name.trim(),
            weight: Number(criterion.weight),
            description: criterion.description.trim() || undefined,
            is_manual: criterion.is_manual,
            sort_order: index,
          });
          createdCriteria += 1;
        }
      } catch (error) {
        const message = error instanceof Error && error.message ? error.message : t("common.retry");
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
      resetToCreateMode();
      toast.success(
        createdCriteria
          ? t("groups.createWithCriteriaSuccess", { count: createdCriteria })
          : t("common.create"),
      );
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
    onSettled: () => {
      void invalidateGroupData();
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      group,
      values,
    }: {
      group: AssignmentGroup;
      values: FormValues;
    }) => {
      await updateGroup(group.id, {
        name: values.name.trim(),
        description: values.description?.trim() || null,
        grade_scale: Number(values.grade_scale),
        enable_auto_score_adjustment: values.enable_auto_score_adjustment,
        is_active: values.is_active,
      });

      const nextCriteria = values.criteria.filter(hasCriterionContent);
      const nextExistingIds = new Set(
        nextCriteria
          .map((criterion) => criterion.criterion_id)
          .filter((criterionId): criterionId is string => Boolean(criterionId)),
      );
      const previousCriteria = group.criteria ?? [];

      for (const criterion of previousCriteria) {
        if (!nextExistingIds.has(criterion.id)) {
          await deleteCriterion(criterion.id);
        }
      }

      for (const [index, criterion] of nextCriteria.entries()) {
        const payload = {
          name: criterion.name.trim(),
          weight: Number(criterion.weight),
          description: criterion.description.trim() || undefined,
          is_manual: criterion.is_manual,
          sort_order: index,
        };
        if (criterion.criterion_id) {
          await updateCriterion(criterion.criterion_id, payload);
        } else {
          await createCriterion(group.id, payload);
        }
      }
    },
    onSuccess: async () => {
      const editedGroupId = editingGroup?.id;
      resetToCreateMode();
      await invalidateGroupData();
      if (editedGroupId) {
        void queryClient.invalidateQueries({ queryKey: ["group", editedGroupId] });
      }
      toast.success(t("groups.updateSuccess"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGroup,
    onSuccess: (_, deletedGroupId) => {
      setGroupPendingDelete(null);
      if (editingGroup?.id === deletedGroupId) {
        resetToCreateMode();
      }
      queryClient.setQueryData(
        ["groups"],
        (currentGroups: Awaited<ReturnType<typeof fetchGroups>> | undefined) =>
          currentGroups?.filter((group) => group.id !== deletedGroupId) ?? currentGroups,
      );
      toast.success(t("groups.deleteSuccess"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
    onSettled: () => {
      void invalidateGroupData();
    },
  });

  const validateWeights = (values: FormValues) => {
    const active = values.criteria.filter(hasCriterionContent);
    const total =
      Math.round(active.reduce((sum, criterion) => sum + (Number(criterion.weight) || 0), 0) * 100) /
      100;

    if (active.length > 0 && Math.round(total * 100) / 100 !== Number(values.grade_scale)) {
      setShowWeightError(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
      return false;
    }

    setShowWeightError(false);
    return true;
  };

  const handleFormSubmit = (values: FormValues) => {
    if (!validateWeights(values)) {
      return;
    }

    if (!editingGroup) {
      createMutation.mutate(values);
      return;
    }

    if ((editingGroup.submissions_count ?? 0) > 0) {
      setPendingEditValues(values);
      return;
    }

    updateMutation.mutate({ group: editingGroup, values });
  };

  const applyPendingEdit = (reviewAfterSave = false) => {
    if (!editingGroup || !pendingEditValues) {
      return;
    }
    const groupId = editingGroup.id;
    updateMutation.mutate(
      { group: editingGroup, values: pendingEditValues },
      {
        onSuccess: () => {
          if (reviewAfterSave) {
            sessionStorage.setItem("activeGroupId", groupId);
            navigate("/submissions");
          }
        },
      },
    );
  };

  const groupsListStyle = groupsListHeight
    ? ({ "--groups-list-height": `${groupsListHeight}px` } as CSSProperties)
    : undefined;

  return (
    <div className="space-y-6">
      <PageHeader title={t("groups.title")} subtitle={t("groups.subtitle")} />
      <div className="grid items-start gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div ref={formCardRef} className="xl:sticky xl:top-28">
        <Card className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">
                {editingGroup ? t("groups.editTitle") : t("common.create")}
              </h3>
              {editingGroup ? (
                <p className="mt-1 text-xs text-foreground/60">
                  {t("groups.editModeHint")}
                </p>
              ) : null}
            </div>
            {editingGroup ? (
              <Button type="button" variant="ghost" onClick={resetToCreateMode}>
                <X size={16} />
                {t("common.cancel")}
              </Button>
            ) : null}
          </div>

          {editingGroup && (editingGroup.submissions_count ?? 0) > 0 ? (
            <div className="mb-4 rounded-xl border border-amber-300/70 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 shrink-0" size={18} />
                <p>{t("groups.editExistingSubmissionsNotice")}</p>
              </div>
            </div>
          ) : null}

          <form className="space-y-4" onSubmit={form.handleSubmit(handleFormSubmit)}>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.name")}</label>
              <Input {...form.register("name")} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.description")}</label>
              <Textarea {...form.register("description")} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.gradeScale")}</label>
              <Input {...form.register("grade_scale")} type="number" onWheel={(e) => e.currentTarget.blur()} />
            </div>
            <label className="flex items-start gap-3 rounded-xl border border-border/70 bg-muted/40 p-3 text-sm">
              <input
                {...form.register("enable_auto_score_adjustment")}
                type="checkbox"
                className="mt-1 size-4"
              />
              <span>
                <span className="block font-medium">{t("groups.autoScoreAdjustment")}</span>
                <span className="mt-1 block text-xs leading-6 text-foreground/60">
                  {t("groups.autoScoreAdjustmentHint")}
                </span>
              </span>
            </label>
            <div className="space-y-4 rounded-2xl border border-border/70 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h4 className="text-sm font-semibold">
                    {editingGroup ? t("groups.criteriaTitle") : t("groups.criteriaCreateTitle")}
                  </h4>
                  <p className="text-xs text-foreground/60">
                    {editingGroup ? t("groups.criteriaEditHint") : t("groups.criteriaCreateHint")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge>{`${t("groups.criteriaCount")}: ${activeCriteriaCount}`}</Badge>
                  <Badge
                    className={
                      isWeightValid ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                    }
                  >
                    {`${t("groups.weights")}: ${criteriaTotal}/${gradeScale}`}
                  </Badge>
                </div>
              </div>

              {showWeightError && activeCriteriaCount > 0 && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  <p className="mb-1 font-semibold">{t("groups.weightTotalValidation")}</p>
                  <p className="text-xs">
                    {criteriaTotal < Number(gradeScale)
                      ? t("groups.weightTooLow", {
                          current: criteriaTotal,
                          required: gradeScale,
                          difference: Number(gradeScale) - criteriaTotal,
                        })
                      : t("groups.weightTooHigh", {
                          current: criteriaTotal,
                          required: gradeScale,
                          difference: criteriaTotal - Number(gradeScale),
                        })}
                  </p>
                </div>
              )}

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
                        <label className="text-sm font-medium">{t("groups.criterionName")}</label>
                        <Input {...form.register(`criteria.${index}.name`)} />
                        {form.formState.errors.criteria?.[index]?.name?.message ? (
                          <p className="text-xs text-destructive">
                            {t(form.formState.errors.criteria[index]?.name?.message as string)}
                          </p>
                        ) : null}
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium">{t("groups.weight")}</label>
                        <Input
                          {...form.register(`criteria.${index}.weight`)}
                          type="number"
                          step="0.01"
                          onWheel={(e) => e.currentTarget.blur()}
                          onChange={(e) => {
                            form.setValue(
                              `criteria.${index}.weight`,
                              e.target.value ? parseFloat(e.target.value) : undefined,
                            );
                          }}
                        />
                        {form.formState.errors.criteria?.[index]?.weight?.message ? (
                          <p className="text-xs text-destructive">
                            {t(form.formState.errors.criteria[index]?.weight?.message as string)}
                          </p>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-4 space-y-2">
                      <label className="text-sm font-medium">{t("groups.description")}</label>
                      <Textarea {...form.register(`criteria.${index}.description`)} className="min-h-20" />
                    </div>

                    <label className="mt-4 flex items-center gap-3 text-sm">
                      <input {...form.register(`criteria.${index}.is_manual`)} type="checkbox" className="size-4" />
                      {t("groups.manual")}
                    </label>
                  </div>
                ))}
              </div>

              <Button variant="ghost" type="button" onClick={() => append(blankCriterion())} className="w-full">
                <Plus size={16} />
                {t("groups.addCriterion")}
              </Button>
            </div>
            <label className="flex items-center gap-3 text-sm">
              <input {...form.register("is_active")} type="checkbox" className="size-4" />
              {t("groups.active")}
            </label>
            <Button className="w-full" disabled={createMutation.isPending || updateMutation.isPending} type="submit">
              {createMutation.isPending || updateMutation.isPending
                ? t("common.loading")
                : editingGroup
                  ? t("groups.saveChanges")
                  : t("common.create")}
            </Button>
          </form>
        </Card>
        </div>

        <div
          className="space-y-4 xl:max-h-[var(--groups-list-height)] xl:overflow-y-auto xl:pe-2"
          style={groupsListStyle}
        >
          {paginatedGroups.length ? (
            paginatedGroups.map((group) => (
              <Card key={group.id} className={editingGroup?.id === group.id ? "border-primary/50 p-5" : "p-5"}>
                <div className="flex flex-col gap-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="min-w-0 text-lg font-semibold leading-7">{group.name}</h3>
                    <Badge
                      className={
                        group.ready_for_evaluation
                          ? "shrink-0 bg-emerald-100 text-emerald-700"
                          : "shrink-0"
                      }
                    >
                      {group.ready_for_evaluation ? t("state.completed") : t("state.pending")}
                    </Badge>
                  </div>

                  {group.description ? (
                    <p
                      dir="auto"
                      className="line-clamp-2 text-start text-sm leading-7 text-foreground/70"
                    >
                      {group.description}
                    </p>
                  ) : null}

                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className="whitespace-nowrap">{`${t("groups.gradeScale")}: ${group.grade_scale}`}</Badge>
                    <Badge className="whitespace-nowrap">{`${t("groups.criteriaCount")}: ${group.criteria?.length ?? 0}`}</Badge>
                    <Badge className="whitespace-nowrap">{`${t("groups.weights")}: ${group.weights_total ?? 0}`}</Badge>
                    <Badge className="whitespace-nowrap">
                      {group.enable_auto_score_adjustment
                        ? t("groups.autoScoreAdjustmentOn")
                        : t("groups.autoScoreAdjustmentOff")}
                    </Badge>
                  </div>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      <Link to={`/groups/${group.id}`}>
                        <Button variant="secondary" className="min-w-28 whitespace-nowrap">
                          <Eye size={16} />
                          {t("groups.details")}
                        </Button>
                      </Link>
                      <Button
                        variant="secondary"
                        type="button"
                        className="min-w-28 whitespace-nowrap"
                        onClick={() => beginEditGroup(group)}
                      >
                        <Pencil size={16} />
                        {t("groups.edit")}
                      </Button>
                    </div>
                    <Button
                      variant="danger"
                      type="button"
                      className="min-w-28 whitespace-nowrap"
                      onClick={() => setGroupPendingDelete(group)}
                      disabled={deleteMutation.isPending && deleteMutation.variables === group.id}
                    >
                      <Trash2 size={16} />
                      {deleteMutation.isPending && deleteMutation.variables === group.id
                        ? t("common.loading")
                        : t("groups.delete")}
                    </Button>
                  </div>
                </div>
              </Card>
            ))
          ) : (
            <EmptyState title={t("groups.title")} description={t("groups.empty")} />
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

      {pendingEditValues && editingGroup ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-xl p-6 shadow-2xl">
            <div className="space-y-5">
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">{t("groups.editImpactTitle")}</h3>
                <p className="text-sm leading-7 text-foreground/75">
                  {t("groups.editImpactDescription", {
                    count: editingGroup.submissions_count ?? 0,
                  })}
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Button type="button" onClick={() => applyPendingEdit(false)} disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? t("common.loading") : t("groups.keepExistingEvaluations")}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => applyPendingEdit(true)}
                  disabled={updateMutation.isPending}
                >
                  {t("groups.saveAndReviewReevaluation")}
                </Button>
              </div>
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => setPendingEditValues(null)}
                disabled={updateMutation.isPending}
              >
                {t("common.cancel")}
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {groupPendingDelete ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-lg p-6 shadow-2xl">
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">{t("groups.deleteDialogTitle")}</h3>
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
                  onClick={() => deleteMutation.mutate(groupPendingDelete.id)}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? t("common.loading") : t("groups.delete")}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
