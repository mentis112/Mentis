import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import { fetchSubmissionEvaluations, reEvaluateSubmission } from "@/services/evaluations";

const DEFAULT_PAGE_SIZE = 10;

export function SubmissionEvaluationsPage() {
  const { t } = useTranslation();
  const { submissionId = "" } = useParams();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const evaluationsQuery = useQuery({
    queryKey: ["submission-evaluations", submissionId],
    queryFn: () => fetchSubmissionEvaluations(submissionId),
    enabled: Boolean(submissionId),
  });
  useEffect(() => {
    setPage(1);
  }, [submissionId]);

  const evaluations = evaluationsQuery.data ?? [];

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(evaluations.length / pageSize));
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [evaluations.length, page, pageSize]);

  const visibleEvaluations = evaluations.slice((page - 1) * pageSize, page * pageSize);

  const reevaluateMutation = useMutation({
    mutationFn: () => reEvaluateSubmission(submissionId),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["submission-evaluations", submissionId] });
      void queryClient.invalidateQueries({ queryKey: ["submissions"] });
      void queryClient.invalidateQueries({ queryKey: ["submission-report"] });
    },
    onSuccess: () => {
      toast.success(t("evaluations.reEvaluate"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t("evaluations.title")} subtitle={t("evaluations.subtitle")} />
      <div className="flex justify-end">
        <Button type="button" onClick={() => reevaluateMutation.mutate()} disabled={reevaluateMutation.isPending}>
          {reevaluateMutation.isPending ? t("common.loading") : t("evaluations.reEvaluate")}
        </Button>
      </div>
      {evaluations.length ? (
        <div className="space-y-4">
          {visibleEvaluations.map((evaluation) => (
            <Card key={evaluation.id} className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap gap-2">
                    <Badge>#{evaluation.evaluation_number}</Badge>
                    {evaluation.is_latest ? <Badge>{t("evaluations.latest")}</Badge> : null}
                  </div>
                  <p className="text-sm text-foreground/70">{evaluation.ai_feedback}</p>
                  <p className="text-sm">
                    {t("evaluations.finalAdjusted")}: {evaluation.final_adjusted_score ?? "-"}
                  </p>
                </div>
                <Link to={`/evaluations/${evaluation.id}`}>
                  <Button variant="secondary">{t("groups.details")}</Button>
                </Link>
              </div>
            </Card>
          ))}
          <PaginationControls
            page={page}
            pageSize={pageSize}
            total={evaluations.length}
            isFetching={evaluationsQuery.isFetching}
            onPageChange={setPage}
            onPageSizeChange={(nextPageSize) => {
              setPageSize(nextPageSize);
              setPage(1);
            }}
          />
        </div>
      ) : (
        <EmptyState title={t("evaluations.title")} description={t("empty.noData")} />
      )}
    </div>
  );
}
