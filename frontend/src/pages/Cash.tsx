import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { CashBookRow, api } from "../lib/api";

export function Cash() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<CashBookRow[]>([]);
  const [balance, setBalance] = useState("0");
  const [operationDate, setOperationDate] = useState(new Date().toISOString().slice(0, 10));
  const [operationType, setOperationType] = useState("cash_in");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  function load() {
    Promise.all([api.cashBalance(), api.cashBook()])
      .then(([cashBalance, book]) => {
        setBalance(cashBalance.balance);
        setRows(book);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiLoadCashError")));
  }

  function create() {
    if (!amount) return;
    api
      .createCashOperation({
        operation_date: operationDate,
        operation_type: operationType,
        amount,
        note: note || null
      })
      .then(() => {
        setAmount("");
        setNote("");
        setError("");
        load();
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiCreateCashError")));
  }

  function cancel(id: number) {
    api
      .cancelCashOperation(id)
      .then(() => {
        setError("");
        load();
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiCancelCashError")));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <PageScaffold title={t("cash")}>
      <div className="panel" style={{ padding: 12, marginBottom: 10 }}>
        <div style={{ color: "#52616f", fontSize: 12 }}>{t("cashBalance")}</div>
        <div style={{ fontSize: 24, fontWeight: 700 }}>{balance}</div>
      </div>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label>{t("date")}</label><input type="date" value={operationDate} onChange={(event) => setOperationDate(event.target.value)} /></div>
        <div className="field">
          <label>{t("type")}</label>
          <select value={operationType} onChange={(event) => setOperationType(event.target.value)}>
            <option value="cash_in">{t("cashIn")}</option>
            <option value="cash_out">{t("cashOut")}</option>
            <option value="correction">{t("correction")}</option>
          </select>
        </div>
        <div className="field"><label>{t("amount")}</label><input value={amount} onChange={(event) => setAmount(event.target.value)} /></div>
        <div className="field"><label>{t("note")}</label><input value={note} onChange={(event) => setNote(event.target.value)} /></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can("cash.create") ? t("noPermission") : ""} disabled={!can("cash.create")} onClick={create}>{t("createOperation")}</button></div>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<CashBookRow>
        rows={rows}
        emptyMessage={t("noCash")}
        searchable
        columns={[
          { key: "operation_date", header: t("date"), sortable: true, render: (row) => formatDate(row.operation_date) },
          { key: "operation_type", header: t("type"), sortable: true, render: (row) => formatCode(row.operation_type, t) },
          { key: "amount", header: t("amount"), sortable: true, render: (row) => formatMoney(row.amount) },
          { key: "partner_name", header: t("partner"), sortable: true },
          { key: "payment_id", header: t("payment"), sortable: true },
          { key: "status", header: t("status"), sortable: true, render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          { key: "balance", header: t("balance"), sortable: true, render: (row) => formatMoney(row.balance) },
          { key: "note", header: t("note") },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <button className="button" title={!can("cash.cancel") ? t("noPermission") : ""} disabled={row.status !== "posted" || !can("cash.cancel")} onClick={() => cancel(row.id)}>{t("cancel")}</button>
            )
          }
        ]}
      />
      <p className="muted-note">
        {t("correctionTodo")}
      </p>
    </PageScaffold>
  );
}
