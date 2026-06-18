import { Settings, SlidersHorizontal, TrendingDown, TrendingUp } from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { Document, Payment, StockBalance, api } from "../lib/api";

type Period = "today" | "week" | "month" | "all";
type WidgetId = "summary" | "finance" | "documentTypes" | "stock" | "payments" | "recentDocuments";

type DashboardState = {
  loading: boolean;
  error: boolean;
  productsCount: number | null;
  partnersCount: number | null;
  documents: Document[] | null;
  payments: Payment[] | null;
  stockBalances: StockBalance[] | null;
  cashBalance: string | null;
};

type WidgetConfig = {
  id: WidgetId;
  title: string;
  description: string;
};

const initialState: DashboardState = {
  loading: true,
  error: false,
  productsCount: null,
  partnersCount: null,
  documents: null,
  payments: null,
  stockBalances: null,
  cashBalance: null,
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

async function loadIfAllowed<T>(allowed: boolean, loader: () => Promise<T>): Promise<T | null> {
  if (!allowed) return null;
  return loader();
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

function isInPeriod(dateValue: string, period: Period) {
  const start = periodStart(period);
  if (!start) return true;
  const date = new Date(`${dateValue.slice(0, 10)}T00:00:00`);
  return date >= start;
}

function sumDocuments(documents: Document[], type: string) {
  return documents
    .filter((document) => document.document_type === type && document.status === "posted")
    .reduce((sum, document) => sum + toNumber(document.total_amount), 0);
}

function countBy<T extends string>(values: T[]) {
  return values.reduce<Record<T, number>>((acc, value) => {
    acc[value] = (acc[value] ?? 0) + 1;
    return acc;
  }, {} as Record<T, number>);
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

    Promise.all([
      loadIfAllowed(can("products.read"), api.products),
      loadIfAllowed(can("partners.read"), () => api.partners()),
      loadIfAllowed(can("documents.read"), api.documents),
      loadIfAllowed(can("payments.read"), api.payments),
      loadIfAllowed(can("stock.read"), api.stockBalances),
      loadIfAllowed(can("cash.read"), api.cashBalance),
    ])
      .then(([products, partners, documents, payments, stockBalances, cashBalance]) => {
        if (cancelled) return;
        setState({
          loading: false,
          error: false,
          productsCount: products?.length ?? null,
          partnersCount: partners?.length ?? null,
          documents,
          payments,
          stockBalances,
          cashBalance: cashBalance?.balance ?? null,
        });
      })
      .catch(() => {
        if (cancelled) return;
        setState((current) => ({ ...current, loading: false, error: true }));
      });

    return () => {
      cancelled = true;
    };
  }, [can]);

  useEffect(() => {
    localStorage.setItem("buy-modern-dashboard-widgets", JSON.stringify(visibleWidgets));
  }, [visibleWidgets]);

  const dashboard = useMemo(() => {
    const allDocuments = state.documents ?? [];
    const documents = allDocuments.filter((document) => isInPeriod(document.document_date, period));
    const payments = (state.payments ?? []).filter((payment) => isInPeriod(payment.payment_date, period));
    const stockBalances = state.stockBalances ?? [];
    const outgoingTotal = sumDocuments(documents, "outgoing");
    const incomingTotal = sumDocuments(documents, "incoming");
    const transferCount = documents.filter((document) => document.document_type === "transfer").length;
    const draftDocuments = documents.filter((document) => document.status === "draft").length;
    const postedDocuments = documents.filter((document) => document.status === "posted").length;
    const cancelledDocuments = documents.filter((document) => document.status === "cancelled").length;
    const documentTypes = countBy(documents.map((document) => document.document_type));
    const paymentStatuses = countBy(payments.map((payment) => payment.status));
    const totalStockQuantity = stockBalances.reduce((sum, row) => sum + toNumber(row.quantity), 0);
    const stockByWarehouse = stockBalances.reduce<Record<string, number>>((acc, row) => {
      const name = row.warehouse_name ?? `#${row.warehouse_id}`;
      acc[name] = (acc[name] ?? 0) + toNumber(row.quantity);
      return acc;
    }, {});
    const topWarehouses = Object.entries(stockByWarehouse)
      .sort(([, left], [, right]) => right - left)
      .slice(0, 5);
    const recentDocuments = [...documents]
      .sort((left, right) => right.document_date.localeCompare(left.document_date) || right.id - left.id)
      .slice(0, 6);

    return {
      documents,
      payments,
      outgoingTotal,
      incomingTotal,
      grossDelta: outgoingTotal - incomingTotal,
      draftDocuments,
      postedDocuments,
      cancelledDocuments,
      transferCount,
      documentTypes,
      paymentStatuses,
      totalStockQuantity,
      topWarehouses,
      recentDocuments,
    };
  }, [period, state.documents, state.payments, state.stockBalances]);

  const visible = (id: WidgetId) => visibleWidgets.includes(id);
  const placeholder = state.loading ? t("loading") : "-";

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
          <MetricCard accent="green" label="Продажи" value={state.documents ? formatMoney(dashboard.outgoingTotal) : placeholder} hint="Проведённые расходы" />
          <MetricCard accent="yellow" label="Закупки" value={state.documents ? formatMoney(dashboard.incomingTotal) : placeholder} hint="Проведённые приходы" />
          <MetricCard accent="violet" label="Черновики" value={state.documents ? String(dashboard.draftDocuments) : placeholder} hint="Ждут обработки" />
          <MetricCard accent="blue" label="Позиции склада" value={state.stockBalances ? String(state.stockBalances.length) : placeholder} hint={`${formatMoney(dashboard.totalStockQuantity)} ед. всего`} />
          <MetricCard accent="slate" label="Контрагенты" value={state.partnersCount === null ? placeholder : String(state.partnersCount)} hint="Клиенты и поставщики" />
          <MetricCard accent="slate" label="Товары" value={state.productsCount === null ? placeholder : String(state.productsCount)} hint="Активный справочник" />
        </div>
      ) : null}

      <div className="dashboard-grid">
        {visible("finance") ? (
          <section className="dashboard-widget dashboard-widget-wide">
            <WidgetHeader title="Деньги и документы" action={<SlidersHorizontal size={18} />} />
            <div className="dashboard-finance">
              <div>
                <div className="dashboard-big-number">{state.cashBalance === null ? placeholder : formatMoney(state.cashBalance)}</div>
                <div className="dashboard-subtitle">Остаток кассы</div>
              </div>
              <div className={`dashboard-delta ${dashboard.grossDelta >= 0 ? "positive" : "negative"}`}>
                {dashboard.grossDelta >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                {formatMoney(dashboard.grossDelta)}
              </div>
            </div>
            <div className="dashboard-bars">
              <ProgressRow color="#19c37d" label="Проведено" value={dashboard.postedDocuments} total={dashboard.documents.length} />
              <ProgressRow color="#8b5cf6" label="Черновики" value={dashboard.draftDocuments} total={dashboard.documents.length} />
              <ProgressRow color="#ef4444" label="Отменено" value={dashboard.cancelledDocuments} total={dashboard.documents.length} />
            </div>
          </section>
        ) : null}

        {visible("documentTypes") ? (
          <section className="dashboard-widget dashboard-widget-chart">
            <WidgetHeader title="Структура документов" />
            <div className="dashboard-rings" aria-label="Разбивка документов по типам">
              <Ring value={dashboard.documentTypes.incoming ?? 0} total={dashboard.documents.length} color="#f4c542" label={t("incoming")} />
              <Ring value={dashboard.documentTypes.outgoing ?? 0} total={dashboard.documents.length} color="#22c55e" label={t("outgoing")} />
              <Ring value={dashboard.documentTypes.adjustment ?? 0} total={dashboard.documents.length} color="#3b82f6" label={t("adjustment")} />
              <Ring value={dashboard.transferCount} total={dashboard.documents.length} color="#8b5cf6" label={t("transfer")} />
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
