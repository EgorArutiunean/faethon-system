import {
  HandCoins,
  PackagePlus,
  ReceiptText,
  Settings,
  ShoppingCart,
  SlidersHorizontal,
  TrendingDown,
  TrendingUp
} from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { DashboardSummary, api } from "../lib/api";

type Period = "today" | "week" | "month" | "all";
type WidgetId = "summary" | "finance" | "documentTypes" | "stock" | "payments" | "recentDocuments";

type DashboardState = {
  loading: boolean;
  error: boolean;
  summary: DashboardSummary | null;
};

type WidgetConfig = {
  id: WidgetId;
  title: string;
  description: string;
};

const initialState: DashboardState = {
  loading: true,
  error: false,
  summary: null,
};

const widgetConfigs: WidgetConfig[] = [
  { id: "summary", title: "Ключевые показатели", description: "Оборот, черновики и остатки" },
  { id: "finance", title: "Деньги и документы", description: "Приход, расход и касса" },
  { id: "documentTypes", title: "Структура документов", description: "Разбивка по типам и статусам" },
  { id: "stock", title: "Складские позиции", description: "Где сосредоточен товар" },
  { id: "payments", title: "Оплаты", description: "Черновики, проведённые и отменённые" },
  { id: "recentDocuments", title: "Последние документы", description: "Оперативная лента" },
];

const defaultVisibleWidgets: WidgetId[] = widgetConfigs.map((widget) => widget.id);

function loadVisibleWidgets(): WidgetId[] {
  const raw = localStorage.getItem("buy-modern-dashboard-widgets");
  if (!raw) return defaultVisibleWidgets;
  try {
    const parsed = JSON.parse(raw) as WidgetId[];
    const known = parsed.filter((id) => widgetConfigs.some((widget) => widget.id === id));
    return known.length ? known : defaultVisibleWidgets;
  } catch {
    return defaultVisibleWidgets;
  }
}

function toNumber(value?: string | number | null) {
  const numeric = Number(value ?? 0);
  return Number.isNaN(numeric) ? 0 : numeric;
}

function periodStart(period: Period) {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (period === "today") return start;
  if (period === "week") {
    const day = start.getDay() || 7;
    start.setDate(start.getDate() - day + 1);
    return start;
  }
  if (period === "month") return new Date(now.getFullYear(), now.getMonth(), 1);
  return null;
}

function periodStartValue(period: Period) {
  const start = periodStart(period);
  if (!start) return undefined;
  const year = start.getFullYear();
  const month = String(start.getMonth() + 1).padStart(2, "0");
  const day = String(start.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function percent(value: number, total: number) {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}

export function Dashboard() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [state, setState] = useState<DashboardState>(initialState);
  const [period, setPeriod] = useState<Period>("month");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [visibleWidgets, setVisibleWidgets] = useState<WidgetId[]>(loadVisibleWidgets);

  useEffect(() => {
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: false }));

    api.dashboardSummary(periodStartValue(period))
      .then((summary) => {
        if (cancelled) return;
        setState({
          loading: false,
          error: false,
          summary,
        });
      })
      .catch(() => {
        if (cancelled) return;
        setState((current) => ({ ...current, loading: false, error: true }));
      });

    return () => {
      cancelled = true;
    };
  }, [period]);

  useEffect(() => {
    localStorage.setItem("buy-modern-dashboard-widgets", JSON.stringify(visibleWidgets));
  }, [visibleWidgets]);

  const dashboard = useMemo(() => {
    const summary = state.summary;
    const documentTypes = summary?.document_types ?? {};
    const documentStatuses = summary?.document_statuses ?? {};
    const outgoingTotal = toNumber(summary?.outgoing_total);
    const incomingTotal = toNumber(summary?.incoming_total);

    return {
      documentsCount: summary?.documents_count ?? 0,
      outgoingTotal,
      incomingTotal,
      grossDelta: outgoingTotal - incomingTotal,
      draftDocuments: documentStatuses.draft ?? 0,
      postedDocuments: documentStatuses.posted ?? 0,
      cancelledDocuments: documentStatuses.cancelled ?? 0,
      transferCount: documentTypes.transfer ?? 0,
      documentTypes,
      paymentStatuses: summary?.payment_statuses ?? {},
      totalStockQuantity: toNumber(summary?.stock_total_quantity),
      topWarehouses: (summary?.top_warehouses ?? []).map((row) => [row.name, toNumber(row.quantity)] as [string, number]),
      recentDocuments: summary?.recent_documents ?? [],
    };
  }, [state.summary]);

  const visible = (id: WidgetId) => visibleWidgets.includes(id);
  const placeholder = state.loading ? t("loading") : "-";
  const quickActions = [
    { label: "Новая продажа", to: "/documents?create=outgoing", icon: ShoppingCart, permission: "documents.create" },
    { label: "Новый приход", to: "/documents?create=incoming", icon: PackagePlus, permission: "documents.create" },
    { label: "Принять оплату", to: "/payments?create=customer_payment", icon: HandCoins, permission: "payments.create" },
    { label: "Записать расход", to: "/cash?create=cash_out", icon: ReceiptText, permission: "cash.create" },
  ].filter((action) => can(action.permission));

  function toggleWidget(id: WidgetId) {
    setVisibleWidgets((current) => {
      if (current.includes(id)) {
        return current.length === 1 ? current : current.filter((widgetId) => widgetId !== id);
      }
      return [...current, id];
    });
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-hero">
        <div>
          <div className="dashboard-kicker">Рабочая панель</div>
          <h1>Панель управления</h1>
          <p>Оперативная картина по продажам, закупкам, складу и оплатам.</p>
        </div>
        <div className="dashboard-actions">
          <div className="dashboard-periods" aria-label="Период отчёта">
            {[
              ["today", "Сегодня"],
              ["week", "Неделя"],
              ["month", "Месяц"],
              ["all", "Всё"],
            ].map(([value, label]) => (
              <button key={value} className={period === value ? "active" : ""} onClick={() => setPeriod(value as Period)}>
                {label}
              </button>
            ))}
          </div>
          <button className="dashboard-settings-button" onClick={() => setSettingsOpen((value) => !value)}>
            <Settings size={17} />
            Настроить
          </button>
        </div>
      </div>

      {quickActions.length ? (
        <section className="dashboard-command-bar" aria-label="Быстрые действия менеджера">
          <h2>Быстрые действия</h2>
          <div className="dashboard-command-list">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Link className="dashboard-command" key={action.to} to={action.to}>
                  <Icon size={17} />
                  <span>{action.label}</span>
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      {state.error ? (
        <div className="panel error-panel">{t("apiLoadDashboardError")}</div>
      ) : null}

      {settingsOpen ? (
        <div className="dashboard-settings panel">
          <div>
            <strong>Виджеты на экране</strong>
            <p>Выберите блоки, которые нужны на рабочем месте. Настройка сохраняется в этом браузере.</p>
          </div>
          <div className="dashboard-widget-toggles">
            {widgetConfigs.map((widget) => (
              <label key={widget.id} className="dashboard-toggle">
                <input checked={visibleWidgets.includes(widget.id)} type="checkbox" onChange={() => toggleWidget(widget.id)} />
                <span>
                  <strong>{widget.title}</strong>
                  <small>{widget.description}</small>
                </span>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {visible("summary") ? (
        <div className="dashboard-summary-grid">
          <MetricCard accent="green" label="Продажи" value={state.summary?.outgoing_total == null ? placeholder : formatMoney(dashboard.outgoingTotal)} hint="Проведённые расходы" />
          <MetricCard accent="yellow" label="Закупки" value={state.summary?.incoming_total == null ? placeholder : formatMoney(dashboard.incomingTotal)} hint="Проведённые приходы" />
          <MetricCard accent="violet" label="Черновики" value={state.summary?.document_statuses == null ? placeholder : String(dashboard.draftDocuments)} hint="Ждут обработки" />
          <MetricCard accent="blue" label="Позиции склада" value={state.summary?.stock_positions_count == null ? placeholder : String(state.summary.stock_positions_count)} hint={`${formatMoney(dashboard.totalStockQuantity)} ед. всего`} />
          <MetricCard accent="slate" label="Контрагенты" value={state.summary?.partners_count == null ? placeholder : String(state.summary.partners_count)} hint="Клиенты и поставщики" />
          <MetricCard accent="slate" label="Товары" value={state.summary?.products_count == null ? placeholder : String(state.summary.products_count)} hint="Активный справочник" />
        </div>
      ) : null}

      <div className="dashboard-grid">
        {visible("finance") ? (
          <section className="dashboard-widget dashboard-widget-wide">
            <WidgetHeader title="Деньги и документы" action={<SlidersHorizontal size={18} />} />
            <div className="dashboard-finance">
              <div>
                <div className="dashboard-big-number">{state.summary?.cash_balance == null ? placeholder : formatMoney(state.summary.cash_balance)}</div>
                <div className="dashboard-subtitle">Остаток кассы</div>
              </div>
              <div className={`dashboard-delta ${dashboard.grossDelta >= 0 ? "positive" : "negative"}`}>
                {dashboard.grossDelta >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                {formatMoney(dashboard.grossDelta)}
              </div>
            </div>
            <div className="dashboard-bars">
              <ProgressRow color="#19c37d" label="Проведено" value={dashboard.postedDocuments} total={dashboard.documentsCount} />
              <ProgressRow color="#8b5cf6" label="Черновики" value={dashboard.draftDocuments} total={dashboard.documentsCount} />
              <ProgressRow color="#ef4444" label="Отменено" value={dashboard.cancelledDocuments} total={dashboard.documentsCount} />
            </div>
          </section>
        ) : null}

        {visible("documentTypes") ? (
          <section className="dashboard-widget dashboard-widget-chart">
            <WidgetHeader title="Структура документов" />
            <div className="dashboard-rings" aria-label="Разбивка документов по типам">
              <Ring value={dashboard.documentTypes.incoming ?? 0} total={dashboard.documentsCount} color="#f4c542" label={t("incoming")} />
              <Ring value={dashboard.documentTypes.outgoing ?? 0} total={dashboard.documentsCount} color="#22c55e" label={t("outgoing")} />
              <Ring value={dashboard.documentTypes.adjustment ?? 0} total={dashboard.documentsCount} color="#3b82f6" label={t("adjustment")} />
              <Ring value={dashboard.transferCount} total={dashboard.documentsCount} color="#8b5cf6" label={t("transfer")} />
            </div>
          </section>
        ) : null}

        {visible("stock") ? (
          <section className="dashboard-widget">
            <WidgetHeader title="Склады" />
            <div className="dashboard-list">
              {dashboard.topWarehouses.length ? dashboard.topWarehouses.map(([name, quantity]) => (
                <ProgressRow key={name} color="#0ea5e9" label={name} value={quantity} total={dashboard.totalStockQuantity} />
              )) : <div className="dashboard-empty">Нет складских остатков</div>}
            </div>
          </section>
        ) : null}

        {visible("payments") ? (
          <section className="dashboard-widget">
            <WidgetHeader title="Оплаты" />
            <div className="dashboard-payment-grid">
              <MiniStat label={t("draft")} value={dashboard.paymentStatuses.draft ?? 0} />
              <MiniStat label={t("posted")} value={dashboard.paymentStatuses.posted ?? 0} />
              <MiniStat label={t("cancelled")} value={dashboard.paymentStatuses.cancelled ?? 0} />
            </div>
            <Link className="dashboard-link" to="/payments">Открыть оплаты</Link>
          </section>
        ) : null}

        {visible("recentDocuments") ? (
          <section className="dashboard-widget dashboard-widget-wide">
            <WidgetHeader title="Последние документы" />
            <div className="dashboard-document-list">
              {dashboard.recentDocuments.length ? dashboard.recentDocuments.map((document) => (
                <Link className="dashboard-document-row" key={document.id} to={`/documents/${document.id}`}>
                  <span>
                    <strong>{document.number || `#${document.id}`}</strong>
                    <small>{formatCode(document.document_type, t)} · {formatDate(document.document_date)} · {document.partner_name ?? t("notSelected")}</small>
                  </span>
                  <span>
                    <StatusBadge status={document.status} label={formatCode(document.status, t)} />
                    <b>{formatMoney(document.total_amount)}</b>
                  </span>
                </Link>
              )) : <div className="dashboard-empty">За выбранный период документов нет</div>}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function WidgetHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="dashboard-widget-header">
      <h2>{title}</h2>
      {action ? <span>{action}</span> : null}
    </div>
  );
}

function MetricCard({ accent, label, value, hint }: { accent: string; label: string; value: string; hint: string }) {
  return (
    <div className={`dashboard-metric ${accent}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="dashboard-mini-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ProgressRow({ color, label, value, total }: { color: string; label: string; value: number; total: number }) {
  const width = percent(value, total);
  const valueLabel = Number.isInteger(value) ? value.toLocaleString() : formatMoney(value);
  return (
    <div className="dashboard-progress-row">
      <div>
        <span>{label}</span>
        <strong>{valueLabel}</strong>
      </div>
      <div className="dashboard-progress-track">
        <i style={{ backgroundColor: color, width: `${width}%` }} />
      </div>
    </div>
  );
}

function Ring({ color, label, total, value }: { color: string; label: string; total: number; value: number }) {
  const size = 132;
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent(value, total) / 100) * circumference;
  return (
    <div className="dashboard-ring">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} fill="none" r={radius} stroke="rgba(148, 163, 184, 0.22)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          fill="none"
          r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth={stroke}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text dominantBaseline="middle" fill="#e5eef8" fontSize="22" fontWeight="700" textAnchor="middle" x="50%" y="48%">
          {value}
        </text>
      </svg>
      <span>{label}</span>
    </div>
  );
}
