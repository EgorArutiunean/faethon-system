import {
  BarChart3, Boxes, Building2, ChevronRight, CircleDollarSign, ClipboardList,
  FileText, History, Home, Menu, Package, PanelLeftClose, PanelLeftOpen,
  Settings, Truck, UserRound, Users, WalletCards, X
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth";
import { formatCode } from "../format";
import { useI18n } from "../i18n";

const sections = [
  { id: "home", labelKey: "sectionHome" },
  { id: "documents", labelKey: "sectionSales" },
  { id: "catalog", labelKey: "sectionCatalog" },
  { id: "warehouse", labelKey: "sectionWarehouse" },
  { id: "finance", labelKey: "sectionFinance" },
  { id: "reports", labelKey: "sectionReports" },
  { id: "system", labelKey: "sectionSettings" }
] as const;

const nav = [
  { to: "/", labelKey: "dashboard", icon: Home, section: "home" },
  { to: "/documents", labelKey: "documents", icon: ClipboardList, permission: "documents.read", section: "documents" },
  { to: "/partners", labelKey: "partners", icon: Users, permission: "partners.read", section: "catalog" },
  { to: "/products", labelKey: "products", icon: Package, permission: "products.read", section: "catalog" },
  { to: "/warehouses", labelKey: "warehouses", icon: Building2, permission: "warehouses.read", section: "warehouse" },
  { to: "/stock", labelKey: "stock", icon: Boxes, permission: "stock.read", section: "warehouse" },
  { to: "/logistics", labelKey: "logistics", icon: Truck, permission: "logistics.read", section: "warehouse" },
  { to: "/payments", labelKey: "payments", icon: WalletCards, permission: "payments.read", section: "finance" },
  { to: "/cash", labelKey: "cash", icon: CircleDollarSign, permission: "cash.read", section: "finance" },
  { to: "/reports", labelKey: "reports", icon: BarChart3, permission: "reports.read", section: "reports" },
  { to: "/audit", labelKey: "auditLog", icon: History, permission: "audit.read", section: "system" },
  { to: "/settings", labelKey: "settings", icon: Settings, permission: "settings.manage", section: "system" }
];

type SidebarMode = "expanded" | "collapsed" | "hidden";

function loadSidebarMode(): SidebarMode {
  const stored = localStorage.getItem("buy-modern-sidebar-mode");
  return stored === "collapsed" || stored === "hidden" || stored === "expanded" ? stored : "expanded";
}

export function AppLayout() {
  const { t } = useI18n();
  const { user, logout, can } = useAuth();
  const location = useLocation();
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>(loadSidebarMode);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const visibleNav = nav.filter((item) => !item.permission || can(item.permission));
  const visibleSections = sections.filter((section) => section.id === "home" || visibleNav.some((item) => item.section === section.id));
  const currentItem = visibleNav.find((item) => item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to));
  const currentSection = visibleSections.find((section) => section.id === currentItem?.section) ?? visibleSections[0];
  const isCollapsed = sidebarMode === "collapsed";
  const isHidden = sidebarMode === "hidden";
  const roleLabel = user?.role_names[0] ? formatCode(user.role_names[0], t) : "";
  const userName = user?.full_name?.trim() || user?.email || "";

  useEffect(() => { localStorage.setItem("buy-modern-sidebar-mode", sidebarMode); }, [sidebarMode]);
  useEffect(() => { setMobileMenuOpen(false); }, [location.pathname]);

  return (
    <div className={`app-shell sidebar-${sidebarMode} ${mobileMenuOpen ? "mobile-menu-open" : ""}`}>
      <header className="header">
        <div className="header-title">
          <button className="mobile-menu-button layout-icon-button" aria-label="Открыть меню" aria-expanded={mobileMenuOpen} onClick={() => setMobileMenuOpen(true)}><Menu size={20} /></button>
          <div className="app-mark"><FileText size={18} /></div>
          <strong>{t("navTitle")}</strong>
          <span className="header-divider" />
          <span className="header-workspace">{t("operationalWorkspace")}</span>
        </div>
        <div className="header-actions">
          <div className="header-user" data-testid="header-user" aria-label={roleLabel ? `${userName}: ${roleLabel}` : userName}>
            <span className="header-user-icon" aria-hidden="true"><UserRound size={16} /></span>
            <span className="header-user-label"><strong className="header-user-name">{userName}{roleLabel ? ":" : ""}</strong>{roleLabel ? <span className="header-user-role">{roleLabel}</span> : null}</span>
          </div>
          <button className="button header-logout" onClick={logout}>{t("logout")}</button>
        </div>
      </header>
      <div className="workspace">
        <aside className="sidebar" aria-label="Навигация">
          <div className="sidebar-title">
            <div className="sidebar-brand"><span>Разделы</span></div>
            <div className="sidebar-controls">
              <button className="sidebar-icon-button" aria-label={isCollapsed ? "Развернуть меню" : "Свернуть меню"} title={isCollapsed ? "Развернуть меню" : "Свернуть меню"} onClick={() => setSidebarMode(isCollapsed ? "expanded" : "collapsed")}><ChevronRight size={17} className={isCollapsed ? "" : "chevron-reverse"} /></button>
              <button className="sidebar-icon-button" aria-label="Скрыть меню" title="Скрыть меню" onClick={() => setSidebarMode("hidden")}><PanelLeftClose size={17} /></button>
            </div>
            <button className="mobile-close-button sidebar-icon-button" aria-label="Закрыть меню" onClick={() => setMobileMenuOpen(false)}><X size={20} /></button>
          </div>
          <nav className="sidebar-nav" aria-label="Команды раздела">
            {visibleSections.map((section) => <div className="sidebar-group" key={section.id}>
              <div className="sidebar-group-label">{t(section.labelKey)}</div>
              {visibleNav.filter((item) => item.section === section.id).map((item) => {
                const Icon = item.icon;
                const label = t(item.labelKey as Parameters<typeof t>[0]);
                return <NavLink key={item.to} to={item.to} end={item.to === "/"} className="nav-link" title={isCollapsed ? label : ""} onClick={() => setMobileMenuOpen(false)}><Icon size={17} /><span>{label}</span></NavLink>;
              })}
            </div>)}
          </nav>
          <button className="button mobile-logout" onClick={logout}>{t("logout")}</button>
        </aside>
        {mobileMenuOpen ? <button className="mobile-menu-scrim" aria-label="Закрыть меню" onClick={() => setMobileMenuOpen(false)} /> : null}
        <main className="main">
          <div className="workplace-bar">
            {isHidden ? <button className="layout-icon-button show-sidebar-button" aria-label="Показать меню" onClick={() => setSidebarMode("expanded")}><PanelLeftOpen size={18} /></button> : null}
            <span>{currentSection ? t(currentSection.labelKey) : ""}</span><ChevronRight size={14} /><strong>{currentItem ? t(currentItem.labelKey as Parameters<typeof t>[0]) : currentSection ? t(currentSection.labelKey) : ""}</strong>
          </div>
          <section className="content"><Outlet /></section>
        </main>
      </div>
    </div>
  );
}
