import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  Bot,
  FolderKanban,
  UploadCloud,
  Plus,
  Calendar,
  Target,
  CheckCircle2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/shared/card";
import { EmptyState } from "@/components/shared/empty-state";
import { StatCard } from "@/components/shared/stat-card";
import { fetchDashboardSummary } from "@/services/dashboard";
import { fetchGroups } from "@/services/groups";
import { Button } from "@/components/shared/button";
import { Badge } from "@/components/shared/badge";

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
  });

  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
  });

  const summary = summaryQuery.data;
  const groups = groupsQuery.data || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <PageHeader
          title={t("dashboard.title")}
          subtitle={t("dashboard.subtitle")}
        />
        <Button onClick={() => navigate("/groups")} className="gap-2">
          <Plus className="h-4 w-4" />
          {t("groups.newGroup", "إنشاء مجموعة واجبات")}
        </Button>
      </div>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label={t("dashboard.totalGroups")}
          value={summary?.total_groups ?? "-"}
          icon={<FolderKanban size={18} />}
        />
        <StatCard
          label={t("dashboard.totalSubmissions")}
          value={summary?.total_submissions ?? "-"}
          icon={<UploadCloud size={18} />}
        />
        <StatCard
          label={t("dashboard.pending")}
          value={summary?.pending_submissions ?? "-"}
          icon={<Activity size={18} />}
        />
        <StatCard
          label={t("dashboard.completed")}
          value={summary?.completed_submissions ?? "-"}
          icon={<Bot size={18} />}
        />
        <StatCard
          label={t("dashboard.failed")}
          value={summary?.failed_submissions ?? "-"}
          icon={<AlertCircle size={18} />}
        />
      </section>

      <section className="grid gap-4">
        <Card className="p-6">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <FolderKanban className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold">
                {t("groups.title", "مجموعات الواجبات")}
              </h3>
            </div>
            <Link
              to="/groups"
              className="text-sm font-medium text-primary hover:underline"
            >
              {t("common.viewAll", "عرض الكل")}
            </Link>
          </div>

          {groupsQuery.isLoading ? (
            <div className="flex justify-center p-8">
              <Activity className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : groups.length ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {groups.slice(0, 6).map((group) => {
                const date = group.created_at
                  ? new Date(group.created_at).toLocaleDateString(
                      t("common.locale", "ar-SA"),
                    )
                  : "";

                return (
                  <Link
                    key={group.id}
                    to={`/groups/${group.id}`}
                    className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-muted-foreground/20 bg-card p-5 transition-all hover:border-primary/50 hover:shadow-md"
                  >
                    <div>
                      <div className="mb-4 flex items-start justify-between gap-4">
                        <div className="rounded-xl bg-primary/10 p-2.5 text-primary">
                          <FolderKanban className="h-5 w-5" />
                        </div>
                        {group.ready_for_evaluation ? (
                          <Badge
                            className="bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25 border-0"
                          >
                            <CheckCircle2 className="mr-1 h-3 w-3 rtl:ml-1 rtl:mr-0" />
                            {t("groups.ready", "جاهز")}
                          </Badge>
                        ) : (
                          <Badge
                            className="bg-amber-500/15 text-amber-600 hover:bg-amber-500/25 border-0"
                          >
                            <AlertCircle className="mr-1 h-3 w-3 rtl:ml-1 rtl:mr-0" />
                            {t("groups.notReady", "غير جاهز")}
                          </Badge>
                        )}
                      </div>

                      <h4 className="font-semibold text-lg mb-1 group-hover:text-primary transition-colors line-clamp-1">
                        {group.name}
                      </h4>
                      {group.description && (
                        <p className="text-sm text-foreground/60 line-clamp-2 mb-4">
                          {group.description}
                        </p>
                      )}
                    </div>

                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-foreground/50 border-t border-border pt-4">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>{date}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Target className="h-3.5 w-3.5" />
                        <span>
                          {group.criteria?.length ?? 0}{" "}
                          {t("groups.criteria", "معايير")}
                        </span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <EmptyState
              icon={
                <FolderKanban size={40} className="text-muted-foreground/50" />
              }
              title={t("groups.emptyTitle", "لا توجد مجموعات")}
              description={t(
                "groups.emptyDescription",
                "قم بإنشاء مجموعة واجبات لبدء تقييم أعمال الطلاب.",
              )}
              action={
                <Button
                  onClick={() => navigate("/groups")}
                  className="mt-4 gap-2"
                >
                  <Plus className="h-4 w-4" />
                  {t("groups.newGroup", "إنشاء مجموعة واجبات")}
                </Button>
              }
            />
          )}
        </Card>
      </section>
    </div>
  );
}
