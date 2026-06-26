import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { Input } from "@/components/shared/input";
import { Textarea } from "@/components/shared/textarea";
import { Badge } from "@/components/shared/badge";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import type { AssignmentGroup, EvaluationCriterion } from "@/types/api";
import { createCriterion, deleteCriterion, fetchGroup, updateCriterion, updateGroup } from "@/services/groups";

const schema = z.object({
  name: z.string().min(2),
  weight: z.coerce.number().positive().max(100),
  description: z.string().optional(),
  is_manual: z.boolean().default(false),
  sort_order: z.coerce.number().min(0),
});

type FormValues = z.infer<typeof schema>;

const roundWeightTotal = (criteria: EvaluationCriterion[] = []) =>
  Math.round(
    criteria.reduce((sum, criterion) => sum + Number(criterion.weight ?? 0), 0) * 100,
  ) / 100;

const sortCriteria = (criteria: EvaluationCriterion[]) =>
  [...criteria].sort((left, right) => left.sort_order - right.sort_order);

const buildUpdatedGroup = (
  currentGroup: AssignmentGroup | undefined,
  nextCriteria: EvaluationCriterion[],
) => {
  if (!currentGroup) {
    return currentGroup;
  }
  const sortedCriteria = sortCriteria(nextCriteria);
  const weightsTotal = roundWeightTotal(sortedCriteria);
  return {
    ...currentGroup,
    criteria: sortedCriteria,
    weights_total: weightsTotal,
    ready_for_evaluation: sortedCriteria.length > 0 && weightsTotal === 100,
  };
};

export function GroupDetailPage() {
  const { t } = useTranslation();
  const { groupId = "" } = useParams();
  const queryClient = useQueryClient();
  const [editingCriterion, setEditingCriterion] = useState<EvaluationCriterion | null>(null);
  const [isEditingGroupName, setIsEditingGroupName] = useState(false);
  const [groupNameDraft, setGroupNameDraft] = useState("");
  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => fetchGroup(groupId),
    enabled: Boolean(groupId),
  });
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { is_manual: false, sort_order: 0, weight: 10 },
  });
  const watchedName = form.watch("name");
  const watchedWeight = form.watch("weight");
  const watchedDescription = form.watch("description");
  const watchedIsManual = form.watch("is_manual");
  const watchedSortOrder = form.watch("sort_order");

  useEffect(() => {
    if (editingCriterion) {
      form.reset({
        name: editingCriterion.name,
        weight: editingCriterion.weight,
        description: editingCriterion.description ?? "",
        is_manual: editingCriterion.is_manual,
        sort_order: editingCriterion.sort_order,
      });
    } else {
      form.reset({ name: "", weight: 10, description: "", is_manual: false, sort_order: 0 });
    }
  }, [editingCriterion, form]);

  useEffect(() => {
    if (groupQuery.data && !isEditingGroupName) {
      setGroupNameDraft(groupQuery.data.name);
    }
  }, [groupQuery.data, isEditingGroupName]);

  const syncGroupCaches = (updateCriteria: (criteria: EvaluationCriterion[]) => EvaluationCriterion[]) => {
    queryClient.setQueryData<AssignmentGroup | undefined>(["group", groupId], (currentGroup) =>
      buildUpdatedGroup(currentGroup, updateCriteria(currentGroup?.criteria ?? [])),
    );
    queryClient.setQueryData<AssignmentGroup[]>(["groups"], (currentGroups) =>
      currentGroups?.map((currentGroup) =>
        currentGroup.id === groupId
          ? buildUpdatedGroup(currentGroup, updateCriteria(currentGroup.criteria ?? [])) ?? currentGroup
          : currentGroup,
      ) ?? currentGroups,
    );
  };

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => createCriterion(groupId, values),
    onSuccess: (createdCriterion) => {
      syncGroupCaches((criteria) => [...criteria, createdCriterion]);
      setEditingCriterion(null);
      toast.success(t("common.create"));
      void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: (values: FormValues) => {
      if (!editingCriterion) {
        throw new Error("No criterion selected");
      }
      return updateCriterion(editingCriterion.id, values);
    },
    onSuccess: (updatedCriterion) => {
      syncGroupCaches((criteria) =>
        criteria.map((criterion) =>
          criterion.id === updatedCriterion.id ? updatedCriterion : criterion,
        ),
      );
      setEditingCriterion(null);
      toast.success(t("common.save"));
      void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCriterion,
    onSuccess: (_, deletedCriterionId) => {
      syncGroupCaches((criteria) =>
        criteria.filter((criterion) => criterion.id !== deletedCriterionId),
      );
      setEditingCriterion((current) =>
        current?.id === deletedCriterionId ? null : current,
      );
      toast.success(t("common.delete"));
      void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const updateGroupMutation = useMutation({
    mutationFn: (name: string) => updateGroup(groupId, { name }),
    onSuccess: (updatedGroup) => {
      queryClient.setQueryData<AssignmentGroup | undefined>(["group", groupId], (currentGroup) =>
        currentGroup ? { ...currentGroup, ...updatedGroup } : updatedGroup,
      );
      queryClient.setQueryData<AssignmentGroup[]>(["groups"], (currentGroups) =>
        currentGroups?.map((currentGroup) =>
          currentGroup.id === updatedGroup.id ? { ...currentGroup, ...updatedGroup } : currentGroup,
        ) ?? currentGroups,
      );
      setIsEditingGroupName(false);
      setGroupNameDraft(updatedGroup.name);
      toast.success(t("common.save"));
      void queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const group = groupQuery.data;
  const beginGroupNameEdit = () => {
    setGroupNameDraft(group?.name ?? "");
    setIsEditingGroupName(true);
  };

  const cancelGroupNameEdit = () => {
    setGroupNameDraft(group?.name ?? "");
    setIsEditingGroupName(false);
  };

  const saveGroupName = () => {
    const trimmedName = groupNameDraft.trim();
    if (trimmedName.length < 2 || updateGroupMutation.isPending) {
      return;
    }
    updateGroupMutation.mutate(trimmedName);
  };

  const liveDraftCriterion = useMemo<EvaluationCriterion | null>(() => {
    const normalizedWeight = Number.isFinite(Number(watchedWeight)) ? Number(watchedWeight) : 0;
    const normalizedSortOrder = Number.isFinite(Number(watchedSortOrder))
      ? Number(watchedSortOrder)
      : group?.criteria?.length ?? 0;

    if (editingCriterion) {
      return {
        ...editingCriterion,
        name: watchedName ?? "",
        weight: normalizedWeight,
        description: watchedDescription?.trim() ? watchedDescription : null,
        is_manual: Boolean(watchedIsManual),
        sort_order: normalizedSortOrder,
      };
    }

    if (!form.formState.isDirty) {
      return null;
    }

    return {
      id: "__draft__",
      group_id: groupId,
      name: watchedName ?? "",
      weight: normalizedWeight,
      description: watchedDescription?.trim() ? watchedDescription : null,
      is_manual: Boolean(watchedIsManual),
      sort_order: normalizedSortOrder,
      created_at: "",
      updated_at: "",
    };
  }, [
    editingCriterion,
    form.formState.isDirty,
    group?.criteria?.length,
    groupId,
    watchedDescription,
    watchedIsManual,
    watchedName,
    watchedSortOrder,
    watchedWeight,
  ]);
  const liveCriteria = useMemo(() => {
    const currentCriteria = group?.criteria ?? [];
    if (!liveDraftCriterion) {
      return sortCriteria(currentCriteria);
    }
    if (editingCriterion) {
      return sortCriteria(
        currentCriteria.map((criterion) =>
          criterion.id === editingCriterion.id ? liveDraftCriterion : criterion,
        ),
      );
    }
    return sortCriteria([...currentCriteria, liveDraftCriterion]);
  }, [editingCriterion, group?.criteria, liveDraftCriterion]);
  const liveWeightsTotal = useMemo(() => roundWeightTotal(liveCriteria), [liveCriteria]);

  return (
    <div className="space-y-6">
      <div className="mb-6 space-y-2">
        {isEditingGroupName ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div className="w-full max-w-2xl space-y-1">
              <label className="text-sm font-medium">{t("groups.name")}</label>
              <Input
                autoFocus
                value={groupNameDraft}
                onChange={(event) => setGroupNameDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    saveGroupName();
                  }
                  if (event.key === "Escape") {
                    cancelGroupNameEdit();
                  }
                }}
              />
            </div>
            <div className="flex gap-2 pt-6">
              <Button
                type="button"
                onClick={saveGroupName}
                disabled={groupNameDraft.trim().length < 2 || updateGroupMutation.isPending}
              >
                {updateGroupMutation.isPending ? t("common.loading") : t("common.save")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={cancelGroupNameEdit}
                disabled={updateGroupMutation.isPending}
              >
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-3xl font-bold tracking-tight">{group?.name ?? t("groups.title")}</h2>
            {group ? (
              <Button
                type="button"
                variant="ghost"
                className="h-10 w-10 px-0"
                onClick={beginGroupNameEdit}
                title={t("providers.edit")}
              >
                <Pencil size={18} />
              </Button>
            ) : null}
          </div>
        )}
        <p className="max-w-3xl text-sm text-foreground/70">
          {group?.description ?? t("groups.subtitle")}
        </p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold">{t("groups.criteriaTitle")}</h3>
            <Badge>{`${t("groups.weights")}: ${liveWeightsTotal}`}</Badge>
          </div>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit((values) =>
              editingCriterion ? updateMutation.mutate(values) : createMutation.mutate(values),
            )}
          >
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.criterionName")}</label>
              <Input {...form.register("name")} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.weight")}</label>
              <Input {...form.register("weight")} type="number" step="0.01" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("groups.description")}</label>
              <Textarea {...form.register("description")} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex items-center gap-3 text-sm">
                <input {...form.register("is_manual")} type="checkbox" className="size-4" />
                {t("groups.manual")}
              </label>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("groups.sortOrder")}</label>
                <Input {...form.register("sort_order")} type="number" />
              </div>
            </div>
            <div className="flex gap-3">
              <Button className="flex-1" type="submit">
                {editingCriterion ? t("common.save") : t("common.create")}
              </Button>
              {editingCriterion ? (
                <Button variant="ghost" type="button" onClick={() => setEditingCriterion(null)}>
                  {t("common.cancel")}
                </Button>
              ) : null}
            </div>
          </form>
        </Card>

        <div className="space-y-4">
          {liveCriteria.map((criterion) => {
            const isDraftCriterion = criterion.id === "__draft__";
            return (
            <Card
              key={criterion.id}
              className={isDraftCriterion ? "border-dashed border-primary/40 bg-primary/5 p-5" : "p-5"}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <h3 className="font-semibold">{criterion.name || t("groups.criterionName")}</h3>
                  <p className="text-sm text-foreground/70">{criterion.description}</p>
                  {isDraftCriterion ? (
                    <p className="text-xs text-foreground/60">{t("groups.pendingCriterionHint")}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Badge>{criterion.weight}</Badge>
                    {criterion.is_manual ? <Badge>{t("groups.manual")}</Badge> : null}
                  </div>
                </div>
                {!isDraftCriterion ? (
                  <div className="flex gap-2">
                    <Button variant="ghost" type="button" onClick={() => setEditingCriterion(criterion)}>
                      <Pencil size={16} />
                    </Button>
                    <Button variant="ghost" type="button" onClick={() => deleteMutation.mutate(criterion.id)}>
                      <Trash2 size={16} />
                    </Button>
                  </div>
                ) : null}
              </div>
            </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
