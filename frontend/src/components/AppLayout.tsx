import {
  BarChart3,
  Boxes,
  Building2,
  CircleDollarSign,
  ClipboardList,
  FileText,
  Home,
  Package,
  Settings,
  Users,
  WalletCards
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

const nav = [
  { to: "/", labelKey: "dashboard", icon: Home },
  { to: "/products", labelKey: "products", icon: Package },
  { to: "/partners", labelKey: "partners", icon: Users },
  { to: "/warehouses", labelKey: "warehouses", icon: Building2 },
  { to: "/documents", labelKey: "documents", icon: ClipboardList },
  { to: "/stock", labelKey: "stock", icon: Boxes },
  { to: "/payments", labelKey: "payments", icon: WalletCards },
  { to: "/cash", labelKey: "cash", icon: CircleDollarSign },
  { to: "/reports", labelKey: "reports", icon: BarChart3 },
  { to: "/settings", labelKey: "settings", icon: Settings }
];

export function AppLayout() {
  const { t } = useI18n();
  const { user, logout, can } = useAuth();
  const visibleNav = nav.filter((item) => item.to !== "/settings" || can("settings.manage"));
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-title">
          <FileText size={18} />
          <span>{t("navTitle")}</span>
        </div>
        <nav style={{ display: "grid", gap: 4, marginTop: 12 }}>
          {visibleNav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to} end={item.to === "/"} className="nav-link">
                <Icon size={16} />
                <span>{t(item.labelKey as Parameters<typeof t>[0])}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main className="main">
        <header className="header">
          <strong>{t("operationalWorkspace")}</strong>
          <div style={{ display: "flex", gap: 8 }}>
            <span style={{ fontSize: 13, color: "#52616f" }}>
              {user?.email} {user?.role_names[0] ? `(${t("role")}: ${user.role_names[0]})` : ""}
            </span>
            <button className="button">{t("sync")}</button>
            <button className="button" onClick={logout}>{t("logout")}</button>
          </div>
        </header>
        <section className="content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
