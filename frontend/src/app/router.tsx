import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { useAuthStore } from "@/app/store/use-auth-store";
import { DashboardPage } from "@/modules/dashboard/pages/dashboard-page";
import { LoginPage } from "@/modules/auth/pages/login-page";
import { RegisterPage } from "@/modules/auth/pages/register-page";
import { GroupsPage } from "@/modules/groups/pages/groups-page";
import { GroupDetailPage } from "@/modules/groups/pages/group-detail-page";
import { SubmissionPage } from "@/modules/submissions/pages/submissions-page";
import { ProviderSettingsPage } from "@/modules/providers/pages/provider-settings-page";
import { SettingsPage } from "@/modules/settings/pages/settings-page";
import { SubmissionEvaluationsPage } from "@/modules/evaluations/pages/submission-evaluations-page";
import { EvaluationDetailPage } from "@/modules/evaluations/pages/evaluation-detail-page";
import { AllEvaluationsPage } from "@/modules/evaluations/pages/all-evaluations-page";

function AuthOnlyLayout() {
  const token = useAuthStore((state) => state.accessToken);
  return token ? <Navigate to="/" replace /> : <Outlet />;
}

function ProtectedLayout() {
  const token = useAuthStore((state) => state.accessToken);
  return token ? (
    <AppShell>
      <Outlet />
    </AppShell>
  ) : (
    <Navigate to="/login" replace />
  );
}

export const router = createBrowserRouter([
  {
    element: <AuthOnlyLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    path: "/",
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "groups", element: <GroupsPage /> },
      { path: "groups/:groupId", element: <GroupDetailPage /> },
      { path: "submissions", element: <SubmissionPage /> },
      { path: "evaluations", element: <AllEvaluationsPage /> },
      { path: "submissions/:submissionId/evaluations", element: <SubmissionEvaluationsPage /> },
      { path: "evaluations/:evaluationId", element: <EvaluationDetailPage /> },
      { path: "providers", element: <ProviderSettingsPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);
