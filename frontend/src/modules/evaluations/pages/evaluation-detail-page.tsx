import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/shared/badge";
import { Button } from "@/components/shared/button";
import { Card } from "@/components/shared/card";
import { Input } from "@/components/shared/input";
import { getUserFacingErrorMessage } from "@/lib/error-messages";
import { Textarea } from "@/components/shared/textarea";
import { applyManualAdjustments, fetchEvaluationDetail } from "@/services/evaluations";

const optionalNumber = z.preprocess(
  (value) => {
    if (value === "" || value === null || value === undefined || Number.isNaN(value)) {
      return null;
    }
    const parsed = Number(value);
    return Number.isNaN(parsed) ? value : parsed;
  },
  z.number().min(0).nullable(),
);

const schema = z.object({
  items: z.array(
    z.object({
      criterion_score_id: z.string(),
      manual_points: optionalNumber,
      feedback: z.string().nullable(),
    }),
  ),
});

type FormValues = z.infer<typeof schema>;

function toPoints(rawScore: number | null | undefined, weight: number, gradeScale: number) {
  if (rawScore == null || gradeScale <= 0) {
    return null;
  }
  return Math.round(((rawScore / gradeScale) * weight) * 100) / 100;
}

function toRawScore(points: number | null, weight: number, gradeScale: number) {
  if (points == null || weight <= 0) {
    return null;
  }
  return Math.round(((points / weight) * gradeScale) * 100) / 100;
}

export function EvaluationDetailPage() {
  const { t } = useTranslation();
  const { evaluationId = "" } = useParams();
  const queryClient = useQueryClient();
  const evaluationQuery = useQuery({
    queryKey: ["evaluation", evaluationId],
    queryFn: () => fetchEvaluationDetail(evaluationId),
    enabled: Boolean(evaluationId),
  });
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { items: [] },
  });

  useEffect(() => {
    if (evaluationQuery.data) {
      form.reset({
        items: evaluationQuery.data.criterion_scores.map((score) => ({
          criterion_score_id: score.id,
          manual_points: toPoints(score.manual_score, score.weight, evaluationQuery.data.grade_scale),
          feedback: score.feedback,
        })),
      });
    }
  }, [evaluationQuery.data, form]);

  const mutation = useMutation({
    mutationFn: (values: { items: Array<{ criterion_score_id: string; manual_score: number | null; feedback: string | null }> }) =>
      applyManualAdjustments(evaluationId, values),
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ["evaluation", evaluationId] });
      void queryClient.invalidateQueries({ queryKey: ["all-evaluations"] });
      void queryClient.invalidateQueries({ queryKey: ["submission-report"] });
      void queryClient.invalidateQueries({ queryKey: ["submission-evaluations", response.submission_id] });
      toast.success(t("evaluations.applyAdjustments"));
    },
    onError: (error: Error) => toast.error(getUserFacingErrorMessage(error)),
  });

  const evaluation = evaluationQuery.data;
  const gradeScale = evaluation?.grade_scale ?? 100;
  const watchedItems = form.watch("items");
  const liveAdjustedScore = useMemo(() => {
    if (!evaluation) {
      return null;
    }
    const total = evaluation.criterion_scores.reduce((sum, score, index) => {
      const manualPoints = watchedItems[index]?.manual_points;
      const hasManualValue = typeof manualPoints === "number" && Number.isFinite(manualPoints);
      const effectiveScore = hasManualValue
        ? toRawScore(manualPoints, score.weight, gradeScale) ?? 0
        : score.manual_score ?? score.ai_score ?? 0;
      return sum + (score.weight / 100) * effectiveScore;
    }, 0);
    return Math.round(total * 100) / 100;
  }, [evaluation, watchedItems]);

  return (
    <div className="space-y-6">
      <PageHeader title={t("evaluations.title")} subtitle={t("evaluations.subtitle")} />
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-5">
          <div className="mb-4 flex flex-wrap gap-2">
            {evaluation?.is_latest ? <Badge>{t("evaluations.latest")}</Badge> : null}
            {evaluation?.provider_name ? <Badge>{evaluation.provider_name}</Badge> : null}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl bg-muted/70 p-4">
              <p className="text-sm text-foreground/70">{t("evaluations.totalAiScore")}</p>
              <p className="mt-2 text-2xl font-bold">{evaluation?.total_ai_score ?? "-"}</p>
            </div>
            <div className="rounded-2xl bg-muted/70 p-4">
              <p className="text-sm text-foreground/70">{t("evaluations.finalAdjusted")}</p>
              <p className="mt-2 text-2xl font-bold">{evaluation?.final_adjusted_score ?? "-"}</p>
            </div>
          </div>
          <div className="mt-5 space-y-2">
            <h3 className="font-semibold">{t("evaluations.summaryFeedback")}</h3>
            <p className="text-sm leading-7 text-foreground/70">{evaluation?.ai_feedback}</p>
          </div>
        </Card>

        <Card className="p-5" id="manual-adjustments">
          <div className="mb-4 rounded-2xl bg-muted/70 p-4">
            <p className="text-sm font-semibold">{t("evaluations.liveAdjustedPreview")}</p>
            <p className="mt-2 text-2xl font-bold">{liveAdjustedScore ?? "-"}</p>
          </div>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit((values) => {
              if (!evaluation) {
                return;
              }
              const invalidItem = values.items.find((item, index) => {
                const maxWeight = evaluation.criterion_scores[index]?.weight ?? 0;
                return item.manual_points != null && item.manual_points > maxWeight;
              });
              if (invalidItem) {
                const score = evaluation.criterion_scores.find(
                  (criterionScore) => criterionScore.id === invalidItem.criterion_score_id,
                );
                toast.error(
                  t("evaluations.manualPointsRange", {
                    weight: score?.weight ?? 0,
                  }),
                );
                return;
              }
              mutation.mutate({
                items: values.items.map((item, index) => ({
                  criterion_score_id: item.criterion_score_id,
                  manual_score: toRawScore(
                    item.manual_points,
                    evaluation.criterion_scores[index]?.weight ?? 0,
                    gradeScale,
                  ),
                  feedback: item.feedback?.trim() || null,
                })),
              });
            })}
          >
            {evaluation?.criterion_scores.map((score, index) => (
              <div key={score.id} className="rounded-2xl bg-muted/70 p-4">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold">{score.criterion_name}</h3>
                  <Badge>{score.weight}</Badge>
                </div>
                {(() => {
                  const aiPoints = toPoints(score.ai_score, score.weight, gradeScale);
                  const aiPercent = score.ai_score != null && gradeScale > 0
                    ? (score.ai_score / gradeScale) * 100
                    : null;
                  const watchedPoints = watchedItems[index]?.manual_points;
                  const manualPercent = watchedPoints != null && score.weight > 0
                    ? (watchedPoints / score.weight) * 100
                    : null;
                  return (
                    <div className="mb-4 rounded-2xl border border-border/60 bg-background/80 p-3 text-sm text-foreground/70">
                      <p>
                        {t("evaluations.currentAiScore", {
                          points: aiPoints?.toFixed(2) ?? "-",
                          weight: score.weight,
                          percent: aiPercent?.toFixed(1) ?? "-",
                        })}
                      </p>
                      {score.manual_score != null ? (
                        <p className="mt-2">
                          {t("evaluations.currentManualScore", {
                            points: toPoints(score.manual_score, score.weight, gradeScale)?.toFixed(2) ?? "-",
                            weight: score.weight,
                            percent: ((score.manual_score / gradeScale) * 100).toFixed(1),
                          })}
                        </p>
                      ) : null}
                      {manualPercent != null ? (
                        <p className="mt-2">
                          {t("evaluations.manualPercentPreview", {
                            percent: manualPercent.toFixed(1),
                          })}
                        </p>
                      ) : null}
                    </div>
                  );
                })()}
                <div className="grid gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      {t("evaluations.manualScoreOutOfWeight", { weight: score.weight })}
                    </label>
                    <Input
                      {...form.register(`items.${index}.manual_points`)}
                      type="number"
                      step="0.01"
                      placeholder={toPoints(score.ai_score, score.weight, gradeScale)?.toFixed(2) ?? ""}
                    />
                    <input
                      type="hidden"
                      {...form.register(`items.${index}.criterion_score_id`)}
                      value={score.id}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">{t("evaluations.criterionFeedback")}</label>
                    <Textarea {...form.register(`items.${index}.feedback`)} />
                  </div>
                </div>
              </div>
            ))}
            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.loading") : t("evaluations.applyAdjustments")}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
