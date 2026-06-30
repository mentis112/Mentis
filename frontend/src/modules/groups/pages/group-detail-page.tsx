import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  FileText,
  type LucideIcon,
  Pencil,
  Scale,
} from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { cn } from "@/lib/cn";
import { fetchGroup } from "@/services/groups";
import type { EvaluationCriterion } from "@/types/api";

const sortCriteria = (criteria: EvaluationCriterion[]) =>
  [...criteria].sort((left, right) => left.sort_order - right.sort_order);

function OverviewMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/55 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-foreground/55">{label}</span>
        <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon size={18} />
        </span>
      </div>
      <p className="text-2xl font-bold leading-none">{value}</p>
    </div>
  );
}

export function GroupDetailPage() {
  const { t } = useTranslation();
  const { groupId = "" } = useParams();
  const navigate = useNavigate();
  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => fetchGroup(groupId),
    enabled: Boolean(groupId),
  });

  const group = groupQuery.data;
  const criteria = useMemo(() => sortCriteria(group?.criteria ?? []), [group?.criteria]);
  const weightTotal = group?.weights_total ?? 0;
  const isReady = Boolean(group?.ready_for_evaluation);

  if (groupQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Card className="p-6">
          <p className="text-sm text-foreground/65">{t("common.loading")}</p>
        </Card>
      </div>
    );
  }

  if (!group) {
    return <EmptyState title={t("groups.title")} description={t("errors.data.notFound")} />;
  }

  return (
    <div className="space-y-6">
      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <Badge
                  className={cn(
                    isReady ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700",
                  )}
                >
                  {isReady ? t("state.completed") : t("state.pending")}
                </Badge>
                <Badge>
                  {group.enable_auto_score_adjustment
                    ? t("groups.autoScoreAdjustmentOn")
                    : t("groups.autoScoreAdjustmentOff")}
                </Badge>
                <h2 className="break-words text-3xl font-bold tracking-tight">{group.name}</h2>
              </div>
              <p className="max-w-3xl text-sm text-foreground/60">{t("groups.detailsReadOnlyHint")}</p>
            </div>

            <div className="flex flex-wrap gap-2 lg:shrink-0">
              <Button
                type="button"
                variant="secondary"
                onClick={() => navigate("/groups", { state: { editGroupId: group.id } })}
              >
                <Pencil size={16} />
                {t("groups.edit")}
              </Button>
              <Link to="/groups">
                <Button type="button" variant="ghost">
                  <ArrowRight size={16} />
                  {t("groups.backToGroups")}
                </Button>
              </Link>
            </div>
          </div>

          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <OverviewMetric icon={Scale} label={t("groups.gradeScale")} value={group.grade_scale} />
            <OverviewMetric
              icon={ClipboardList}
              label={t("groups.criteriaCount")}
              value={criteria.length}
            />
            <OverviewMetric
              icon={CheckCircle2}
              label={t("groups.weights")}
              value={`${weightTotal}/${group.grade_scale}`}
            />
            <OverviewMetric
              icon={FileText}
              label={t("submissions.title")}
              value={group.submissions_count ?? 0}
            />
          </section>

          <section className="rounded-xl border border-border/70 bg-muted/35 p-4 sm:p-5">
            <div className="mb-3 flex items-center gap-2">
              <FileText size={18} className="text-primary" />
              <h3 className="text-sm font-bold">{t("groups.description")}</h3>
            </div>
            <p
              dir="auto"
              className="max-h-[420px] overflow-y-auto pe-3 whitespace-pre-wrap text-start text-sm leading-8 text-foreground/75 lg:max-h-[460px]"
            >
              {group.description || t("common.notAvailable")}
            </p>
          </section>
        </div>
      </Card>

      <section className="space-y-4">
        <div className="flex flex-col gap-2 border-b border-border/70 pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-2xl font-bold">{t("groups.criteriaTitle")}</h3>
            <p className="mt-1 text-sm text-foreground/60">{t("groups.criteriaDetailsHint")}</p>
          </div>
          <Badge>{`${t("groups.weights")}: ${weightTotal}/${group.grade_scale}`}</Badge>
        </div>

        {criteria.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {criteria.map((criterion, index) => (
              <Card key={criterion.id} className="p-5">
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge>{index + 1}</Badge>
                        {criterion.is_manual ? <Badge>{t("groups.manual")}</Badge> : null}
                      </div>
                      <h4 className="break-words text-lg font-bold">{criterion.name}</h4>
                    </div>
                    <div className="shrink-0 rounded-xl border border-border/70 bg-muted/60 px-3 py-2 text-center">
                      <p className="text-xs font-semibold text-foreground/55">{t("groups.weight")}</p>
                      <p className="text-lg font-bold">{criterion.weight}</p>
                    </div>
                  </div>

                  <p
                    dir="auto"
                    className="min-h-20 whitespace-pre-wrap text-start text-sm leading-7 text-foreground/70"
                  >
                    {criterion.description || t("common.notAvailable")}
                  </p>

                  <div className="flex flex-wrap gap-2 border-t border-border/60 pt-3">
                    <Badge>{`${t("groups.sortOrder")}: ${criterion.sort_order}`}</Badge>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState title={t("groups.criteriaTitle")} description={t("groups.noCriteria")} />
        )}
      </section>
    </div>
  );
}
