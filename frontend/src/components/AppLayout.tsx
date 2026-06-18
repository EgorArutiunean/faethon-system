import {
  BarChart3,
  Boxes,
  Building2,
  CircleDollarSign,
  ClipboardList,
  ChevronsLeft,
  ChevronsRight,
  History,
  FileText,
  Home,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Users,
  WalletCards
} from "lucide-react";
import { useEffect, useState } from "react";
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
  { to: "/audit", labelKey: "auditLog", icon: History },
  { to: "/settings", labelKey: "settings", icon: Settings }
];

type SidebarMode = "expanded" | "collapsed" | "hidden";

function loadSidebarMode(): SidebarMode {
  const stored = localStorage.getItem("buy-modern-sidebar-mode");
  return stored === "collapsed" || stored === "hidden" || stored === "expanded" ? stored : "expanded";
}

export function AppLayout() {
  const { t } = useI18n();
  const { user, logout, can } = useAuth();
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>(loadSidebarMode);
  const visibleNav = nav.filter((item) => {
    if (item.to === "/settings") return can("settings.manage");
    if (item.to === "/audit") return can("audit.read");
    return true;
  });

  useEffect(() => {
    localStorage.setItem("buy-modern-sidebar-mode", sidebarMode);
  }, [sidebarMode]);

  const isCollapsed = sidebarMode === "collapsed";
  const isHidden = sidebarMode === "hidden";

  return (
    <div className={`app-shell sidebar-${sidebarMode}`}>
      {!isHidden ? (
        <aside className="sidebar">
          <div className="sidebar-title">
            <div className="sidebar-brand">
              <FileText size={18} />
              {!isCollapsed ? <span>{t("navTitle")}</span> : null}
            </div>
            <div className="sidebar-controls">
              <button
                aria-label={isCollapsed ? "Развернуть меню" : "Свернуть меню"}
                className="sidebar-icon-button"
                title={isCollapsed ? "Развернуть меню" : "Свернуть меню"}
                onClick={() => setSidebarMode(isCollapsed ? "expanded" : "collapsed")}
              >
                {isCollapsed ? <ChevronsRight size={17} /> : <ChevronsLeft size={17} />}
              </button>
              <button
                aria-label="Скрыть меню"
                className="sidebar-icon-button"
                title="Скрыть меню"
                onClick={() => setSidebarMode("hidden")}
              >
                <PanelLeftClose size={17} />
              </button>
            </div>
          </div>
          <nav className="sidebar-nav">
            {visibleNav.map((item) => {
              const Icon = item.icon;
              const label = t(item.labelKey as Parameters<typeof t>[0]);
              return (
                <NavLink key={item.to} to={item.to} end={item.to === "/"} className="nav-link" title={isCollapsed ? label : ""}>
                  <Icon size={16} />
                  {!isCollapsed ? <span>{label}</span> : null}
                </NavLink>
              );
            })}
          </nav>
        </aside>
      ) : null}
      <main className="main">
        <header className="header">
          <div className="header-title">
            {isHidden ? (
              <button
                aria-label="Показать меню"
                className="layout-icon-button"
                title="Показать меню"
                onClick={() => setSidebarMode("collapsed")}
              >
                <PanelLeftOpen size={18} />
              </button>
            ) : null}
            <strong>{t("operationalWorkspace")}</strong>
          </div>
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
