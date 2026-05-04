import { useI18n } from "../i18n";

export function Dashboard() {
  const { t } = useI18n();
  const metrics = [
    [t("products"), "0"],
    [t("partners"), "0"],
    [t("documents"), "0"],
    [t("pendingPayments"), "0"]
  ];
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(160px, 1fr))", gap: 10 }}>
        {metrics.map(([label, value]) => (
          <div className="panel" key={label} style={{ padding: 12 }}>
            <div style={{ color: "#52616f", fontSize: 12 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>
      <div className="panel" style={{ padding: 12 }}>
        <strong>{t("dailyOperations")}</strong>
        <p style={{ margin: "8px 0 0", color: "#52616f" }}>
          Posting, balance recalculation, and accounting effects are pending legacy rule confirmation.
        </p>
      </div>
    </div>
  );
}
