import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth";
import { useI18n } from "../i18n";

export function ProtectedRoute() {
  const { loading, user } = useAuth();
  const { t } = useI18n();

  if (loading) {
    return <div style={{ padding: 18 }}>{t("loading")}</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
