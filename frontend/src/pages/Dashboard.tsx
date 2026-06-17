import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth";
import { formatMoney } from "../format";
import { useI18n } from "../i18n";
import { api } from "../lib/api";

type DashboardMetric = {
  label: string;
  value: string;
};

type DashboardState = {
  loading: boolean;
  error: boolean;
  products: number | null;
  partners: number | null;
  documents: number | null;
  pendingPayments: number | null;
  stockPositions: number | null;
  cashBalance: string | null;
};

const initialState: DashboardState = {
  loading: true,
  error: false,
  products: null,
  partners: null,
  documents: null,
  pendingPayments: null,
  stockPositions: null,
  cashBalance: null,
};

async function loadIfAllowed<T>(allowed: boolean, loader: () => Promise<T>): Promise<T | null> {
  if (!allowed) return null;
  return loader();
}

export function Dashboard() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [state, setState] = useState<DashboardState>(initialState);

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
          products: products?.length ?? null,
          partners: partners?.length ?? null,
          documents: documents?.length ?? null,
          pendingPayments: payments?.filter((payment) => payment.status === "draft").length ?? null,
          stockPositions: stockBalances?.length ?? null,
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

  const placeholder = state.loading ? t("loading") : "-";
  const metrics = useMemo<DashboardMetric[]>(() => [
    { label: t("products"), value: state.products === null ? placeholder : String(state.products) },
    { label: t("partners"), value: state.partners === null ? placeholder : String(state.partners) },
    { label: t("documents"), value: state.documents === null ? placeholder : String(state.documents) },
    { label: t("pendingPayments"), value: state.pendingPayments === null ? placeholder : String(state.pendingPayments) },
    { label: t("stockPositions"), value: state.stockPositions === null ? placeholder : String(state.stockPositions) },
    { label: t("cashBalance"), value: state.cashBalance === null ? placeholder : formatMoney(state.cashBalance) },
  ], [placeholder, state.cashBalance, state.documents, state.partners, state.pendingPayments, state.products, state.stockPositions, t]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {state.error ? (
        <div className="panel error" style={{ padding: 12 }}>
          {t("apiLoadDashboardError")}
        </div>
      ) : null}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
        {metrics.map(({ label, value }) => (
          <div className="panel" key={label} style={{ padding: 12 }}>
            <div style={{ color: "#52616f", fontSize: 12 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>
      <div className="panel" style={{ padding: 12 }}>
        <strong>{t("dailyOperations")}</strong>
        <p style={{ margin: "8px 0 0", color: "#52616f" }}>
          {t("dashboardOperationsNote")}
        </p>
      </div>
    </div>
  );
}
