import {
  BarChart3,
  Boxes,
  Building2,
  ChevronsLeft,
  ChevronsRight,
  CircleDollarSign,
  ClipboardList,
  FileText,
  History,
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
import { formatCode } from "../format";
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
  const roleLabel = user?.role_names[0] ? formatCode(user.role_names[0], t) : "";
  const collapseLabel = isCollapsed ? "\u0420\u0430\u0437\u0432\u0435\u0440\u043d\u0443\u0442\u044c \u043c\u0435\u043d\u044e" : "\u0421\u0432\u0435\u0440\u043d\u0443\u0442\u044c \u043c\u0435\u043d\u044e";
  const hideLabel = "\u0421\u043a\u0440\u044b\u0442\u044c \u043c\u0435\u043d\u044e";
  const showLabel = "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043c\u0435\u043d\u044e";

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
                aria-label={collapseLabel}
                className="sidebar-icon-button"
                title={collapseLabel}
                onClick={() => setSidebarMode(isCollapsed ? "expanded" : "collapsed")}
              >
                {isCollapsed ? <ChevronsRight size={17} /> : <ChevronsLeft size={17} />}
              </button>
              <button
                aria-label={hideLabel}
                className="sidebar-icon-button"
                title={hideLabel}
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
                aria-label={showLabel}
                className="layout-icon-button"
                title={showLabel}
                onClick={() => setSidebarMode("collapsed")}
              >
                <PanelLeftOpen size={18} />
              </button>
            ) : null}
            <strong>{t("operationalWorkspace")}</strong>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <span style={{ fontSize: 13, color: "#52616f" }}>
              {user?.email} {roleLabel ? `(${t("role")}: ${roleLabel})` : ""}
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
