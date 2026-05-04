import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useI18n } from "../i18n";
import { PartnerBalance, PartnerStatementRow, api } from "../lib/api";

export function PartnerStatement() {
  const { t } = useI18n();
  const { id } = useParams();
  const partnerId = useMemo(() => Number(id), [id]);
  const [balance, setBalance] = useState<PartnerBalance | null>(null);
  const [rows, setRows] = useState<PartnerStatementRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!partnerId) return;
    Promise.all([api.partnerBalance(partnerId), api.partnerStatement(partnerId)])
      .then(([partnerBalance, statement]) => {
        setBalance(partnerBalance);
        setRows(statement);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiLoadStatementError")));
  }, [partnerId]);

  return (
    <PageScaffold title={t("partnerStatement")}>
      <div className="toolbar">
        <Link className="button" to="/partners">{t("backToPartners")}</Link>
        <span style={{ fontSize: 13, color: "#52616f" }}>
          {balance ? `${balance.partner_name}: ${balance.balance}` : ""}
        </span>
      </div>
      {error ? <p style={{ color: "#b42318", fontSize: 13 }}>{error}</p> : null}
      <DataTable<PartnerStatementRow>
        rows={rows}
        emptyMessage={t("noStatement")}
        columns={[
          { key: "date", header: t("date") },
          { key: "source_type", header: t("source") },
          { key: "source_number", header: t("number") },
          { key: "debit", header: t("debit") },
          { key: "credit", header: t("credit") },
          { key: "balance", header: t("balance") },
          { key: "status", header: t("status") }
        ]}
      />
      <p style={{ color: "#52616f", fontSize: 13 }}>
        TODO LEGACY_RULE_REQUIRED: statement ordering, signs, and document-payment matching must be validated against legacy behavior.
      </p>
    </PageScaffold>
  );
}
