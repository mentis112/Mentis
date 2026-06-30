import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/shared/input";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { cn } from "@/lib/cn";
import { fetchEvaluationDetail, fetchAllEvaluations } from "@/services/evaluations";
import { fetchGroups } from "@/services/groups";
import type { AssignmentGroup } from "@/types/api";

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

function GroupFilterDropdown({
  groups,
  value,
  isLoading,
  onChange,
}: {
  groups: AssignmentGroup[];
  value: string;
  isLoading: boolean;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selectedGroup = groups.find((group) => group.id === value);
  const selectedLabel = selectedGroup?.name ?? t("evaluations.allGroups");

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleSelect = (nextValue: string) => {
    onChange(nextValue);
    setIsOpen(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className={cn(
          "flex h-11 w-full items-center justify-between gap-3 rounded-xl border border-border/75 bg-card/70 px-3 text-sm font-bold outline-none transition duration-200 hover:border-foreground/25 focus:border-primary focus:bg-card focus:ring-4 focus:ring-primary/10",
          isOpen && "border-primary bg-card ring-4 ring-primary/10",
        )}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <ChevronDown size={16} className={cn("shrink-0 transition", isOpen && "rotate-180")} />
        <span className="min-w-0 flex-1 truncate text-start">
          {isLoading ? t("common.loading") : selectedLabel}
        </span>
      </button>

      {isOpen ? (
        <div
          role="listbox"
          className="absolute inset-x-0 top-full z-30 mt-2 max-h-80 overflow-y-auto rounded-xl border border-border/75 bg-card/95 p-1.5 shadow-lift backdrop-blur-xl"
        >
          <button
            type="button"
            role="option"
            aria-selected={value === "all"}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-start transition hover:bg-muted/75",
              value === "all" && "bg-primary/10 text-primary",
            )}
            onClick={() => handleSelect("all")}
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center">
              {value === "all" ? <Check size={16} /> : null}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm font-bold">{t("evaluations.allGroups")}</span>
          </button>

          {groups.map((group) => {
            const isSelected = value === group.id;
            const criteriaCount = group.criteria?.length ?? 0;

            return (
              <button
                key={group.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={cn(
                  "flex w-full items-start gap-3 rounded-lg px-3 py-3 text-start transition hover:bg-muted/75",
                  isSelected && "bg-primary/10 text-primary",
                )}
                onClick={() => handleSelect(group.id)}
              >
                <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center">
                  {isSelected ? <Check size={16} /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-bold">{group.name}</span>
                  <span className="mt-1 flex flex-wrap gap-1.5 text-xs text-foreground/60">
                    <span className="rounded-full bg-muted/80 px-2 py-0.5">
                      {`${t("groups.gradeScale")}: ${group.grade_scale}`}
                    </span>
                    <span className="rounded-full bg-muted/80 px-2 py-0.5">
                      {`${t("groups.criteriaCount")}: ${criteriaCount}`}
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5",
                        group.ready_for_evaluation
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-muted/80 text-foreground/60",
                      )}
                    >
                      {group.ready_for_evaluation ? t("state.completed") : t("state.pending")}
                    </span>
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      ) : null}
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
            <GroupFilterDropdown
              groups={groupsQuery.data ?? []}
              value={groupFilter}
              isLoading={groupsQuery.isPending}
              onChange={setGroupFilter}
            />
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
