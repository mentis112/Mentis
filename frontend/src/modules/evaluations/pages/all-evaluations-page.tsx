import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/shared/input";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { Select } from "@/components/shared/select";
import { fetchEvaluationDetail, fetchAllEvaluations } from "@/services/evaluations";
import { fetchGroups } from "@/services/groups";

const DEFAULT_PAGE_SIZE = 10;

function EvaluationInlineDetails({
  evaluationId,
  gradeScale,
}: {
  evaluationId: string;
  gradeScale: number;
}) {
  const { t } = useTranslation();
  const detailQuery = useQuery({
    queryKey: ["evaluation", evaluationId],
    queryFn: () => fetchEvaluationDetail(evaluationId),
    enabled: Boolean(evaluationId),
  });

  if (detailQuery.isPending) {
    return <p className="text-sm text-foreground/60">{t("common.loading")}</p>;
  }

  if (!detailQuery.data) {
    return <p className="text-sm text-foreground/60">{t("empty.noData")}</p>;
  }

  return (
    <div className="space-y-4 rounded-2xl bg-muted/50 p-4">
      <div className="space-y-2">
        <h4 className="font-semibold">{t("evaluations.summaryFeedback")}</h4>
        <p className="text-sm leading-7 text-foreground/70">{detailQuery.data.ai_feedback}</p>
      </div>
      <div className="grid gap-3">
        {detailQuery.data.criterion_scores.map((score) => {
          const rawScore = score.manual_score ?? score.ai_score ?? 0;
          const percent = gradeScale > 0 ? (rawScore / gradeScale) * 100 : 0;
          const points = (score.weight * percent) / 100;
          return (
            <div key={score.id} className="rounded-2xl border border-border/60 bg-background/80 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold">{score.criterion_name}</p>
                <Badge>{score.weight}</Badge>
                <span className="text-xs text-foreground/60">
                  {t("submissions.criterionScoreFormat", {
                    score: points.toFixed(2),
                    weight: score.weight,
                    percent: percent.toFixed(1),
                  })}
                </span>
              </div>
              <p className="mt-2 text-sm leading-7 text-foreground/70">{score.feedback || t("common.notAvailable")}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AllEvaluationsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const evaluationsQuery = useQuery({
    queryKey: ["all-evaluations"],
    queryFn: fetchAllEvaluations,
  });
  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
  });

  const filteredEvaluations = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return (evaluationsQuery.data ?? []).filter((evaluation) => {
      const matchesGroup = groupFilter === "all" || evaluation.group_id === groupFilter;
      if (!matchesGroup) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      return [
        evaluation.submission_filename,
        evaluation.student_id ?? "",
        evaluation.group_name,
        evaluation.provider_name ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedSearch);
    });
  }, [evaluationsQuery.data, groupFilter, search]);

  useEffect(() => {
    setPage(1);
    setExpandedId(null);
  }, [groupFilter, search]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(filteredEvaluations.length / pageSize));
    if (page > totalPages) {
      setPage(totalPages);
      setExpandedId(null);
    }
  }, [filteredEvaluations.length, page, pageSize]);

  const visibleEvaluations = filteredEvaluations.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-6">
      <PageHeader title={t("evaluations.allTitle")} subtitle={t("evaluations.allSubtitle")} />
      <Card className="space-y-4 p-5">
        <div className="grid gap-4 lg:grid-cols-[0.7fr_0.3fr]">
          <div className="space-y-2">
            <label className="text-sm font-medium">{t("evaluations.search")}</label>
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("evaluations.searchPlaceholder")}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">{t("submissions.group")}</label>
            <Select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
              <option value="all">{t("evaluations.allGroups")}</option>
              {groupsQuery.data?.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {visibleEvaluations.length ? (
          <div className="space-y-3">
            {visibleEvaluations.map((evaluation) => (
              <div key={evaluation.id} className="rounded-2xl border border-border/60 bg-background/80 p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <Badge>#{evaluation.evaluation_number}</Badge>
                      {evaluation.is_latest ? <Badge>{t("evaluations.latest")}</Badge> : null}
                      {evaluation.provider_name ? <Badge>{evaluation.provider_name}</Badge> : null}
                    </div>
                    <h3 className="font-semibold">{evaluation.submission_filename}</h3>
                    <p className="text-sm text-foreground/70">
                      {t("common.studentId")}: {evaluation.student_id || t("common.notAvailable")}
                    </p>
                    <p className="text-sm text-foreground/70">
                      {t("groups.title")}: {evaluation.group_name}
                    </p>
                    <div className="flex flex-wrap gap-4 text-sm">
                      <span>
                        {t("evaluations.totalAiScore")}: {evaluation.total_ai_score?.toFixed(2) ?? "-"}
                      </span>
                      <span>
                        {t("evaluations.finalAdjusted")}: {evaluation.final_adjusted_score?.toFixed(2) ?? "-"}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => setExpandedId((current) => (current === evaluation.id ? null : evaluation.id))}
                    >
                      {expandedId === evaluation.id
                        ? t("evaluations.hideInlineDetails")
                        : t("evaluations.showInlineDetails")}
                    </Button>
                    <Link to={`/evaluations/${evaluation.id}`}>
                      <Button variant="ghost" type="button">
                        {t("groups.details")}
                      </Button>
                    </Link>
                    <Link to={`/evaluations/${evaluation.id}#manual-adjustments`}>
                      <Button type="button">{t("submissions.manualAdjust")}</Button>
                    </Link>
                  </div>
                </div>
                {expandedId === evaluation.id ? (
                  <div className="mt-4">
                    <EvaluationInlineDetails evaluationId={evaluation.id} gradeScale={evaluation.grade_scale} />
                  </div>
                ) : null}
              </div>
            ))}

            <PaginationControls
              page={page}
              pageSize={pageSize}
              total={filteredEvaluations.length}
              isFetching={evaluationsQuery.isFetching}
              onPageChange={(nextPage) => {
                setPage(nextPage);
                setExpandedId(null);
              }}
              onPageSizeChange={(nextPageSize) => {
                setPageSize(nextPageSize);
                setPage(1);
                setExpandedId(null);
              }}
            />
          </div>
        ) : (
          <EmptyState title={t("evaluations.allTitle")} description={t("empty.noData")} />
        )}
      </Card>
    </div>
  );
}
