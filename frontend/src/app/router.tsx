import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "@/app/store/use-auth-store";
import { AppShell } from "@/components/layout/app-shell";

const DashboardPage = lazy(() =>
  import("@/modules/dashboard/pages/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  })),
);
const LoginPage = lazy(() =>
  import("@/modules/auth/pages/login-page").then((module) => ({
    default: module.LoginPage,
  })),
);
const RegisterPage = lazy(() =>
  import("@/modules/auth/pages/register-page").then((module) => ({
    default: module.RegisterPage,
  })),
);
const GroupsPage = lazy(() =>
  import("@/modules/groups/pages/groups-page").then((module) => ({
    default: module.GroupsPage,
  })),
);
const GroupDetailPage = lazy(() =>
  import("@/modules/groups/pages/group-detail-page").then((module) => ({
    default: module.GroupDetailPage,
  })),
);
const SubmissionPage = lazy(() =>
  import("@/modules/submissions/pages/submissions-page").then((module) => ({
    default: module.SubmissionPage,
  })),
);
const ProviderSettingsPage = lazy(() =>
  import("@/modules/providers/pages/provider-settings-page").then((module) => ({
    default: module.ProviderSettingsPage,
  })),
);
const SettingsPage = lazy(() =>
  import("@/modules/settings/pages/settings-page").then((module) => ({
    default: module.SettingsPage,
  })),
);
const SubmissionEvaluationsPage = lazy(() =>
  import("@/modules/evaluations/pages/submission-evaluations-page").then(
    (module) => ({ default: module.SubmissionEvaluationsPage }),
  ),
);
const EvaluationDetailPage = lazy(() =>
  import("@/modules/evaluations/pages/evaluation-detail-page").then(
    (module) => ({ default: module.EvaluationDetailPage }),
  ),
);
const AllEvaluationsPage = lazy(() =>
  import("@/modules/evaluations/pages/all-evaluations-page").then((module) => ({
    default: module.AllEvaluationsPage,
  })),
);

function PageFallback() {
  return (
    <div className="flex min-h-48 items-center justify-center text-sm text-foreground/60">
      Loading...
    </div>
  );
}

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>;
}

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
      {
        path: "/login",
        element: (
          <LazyPage>
            <LoginPage />
          </LazyPage>
        ),
      },
      {
        path: "/register",
        element: (
          <LazyPage>
            <RegisterPage />
          </LazyPage>
        ),
      },
    ],
  },
  {
    path: "/",
    element: <ProtectedLayout />,
    children: [
      {
        index: true,
        element: (
          <LazyPage>
            <DashboardPage />
          </LazyPage>
        ),
      },
      {
        path: "groups",
        element: (
          <LazyPage>
            <GroupsPage />
          </LazyPage>
        ),
      },
      {
        path: "groups/:groupId",
        element: (
          <LazyPage>
            <GroupDetailPage />
          </LazyPage>
        ),
      },
      {
        path: "submissions",
        element: (
          <LazyPage>
            <SubmissionPage />
          </LazyPage>
        ),
      },
      {
        path: "evaluations",
        element: (
          <LazyPage>
            <AllEvaluationsPage />
          </LazyPage>
        ),
      },
      {
        path: "submissions/:submissionId/evaluations",
        element: (
          <LazyPage>
            <SubmissionEvaluationsPage />
          </LazyPage>
        ),
      },
      {
        path: "evaluations/:evaluationId",
        element: (
          <LazyPage>
            <EvaluationDetailPage />
          </LazyPage>
        ),
      },
      {
        path: "providers",
        element: (
          <LazyPage>
            <ProviderSettingsPage />
          </LazyPage>
        ),
      },
      {
        path: "settings",
        element: (
          <LazyPage>
            <SettingsPage />
          </LazyPage>
        ),
      },
    ],
  },
]);
