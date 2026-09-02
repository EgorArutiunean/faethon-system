import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth";
import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import {
  Partner,
  PartnerBalance,
  Payment,
  PaymentAllocationInput,
  PaymentAllocationOption,
  PaymentWrite,
  api
} from "../lib/api";

type AllocationValues = Record<number, string>;

function allocationInputs(values: AllocationValues): PaymentAllocationInput[] {
  return Object.entries(values)
    .map(([documentId, value]) => ({ document_id: Number(documentId), amount: value }))
    .filter((allocation) => Number(allocation.amount) > 0);
}

export function Payments() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<Payment[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [balances, setBalances] = useState<PartnerBalance[]>([]);
  const [allocationOptions, setAllocationOptions] = useState<PaymentAllocationOption[]>([]);
  const [allocations, setAllocations] = useState<AllocationValues>({});
  const [partnerId, setPartnerId] = useState("");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [paymentType, setPaymentType] = useState("customer_payment");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [allocatingPaymentId, setAllocatingPaymentId] = useState<number | null>(null);

  const canAllocate = can("payments.allocate");
  const isPostedAllocation = allocatingPaymentId !== null;
  const partnerOptions = useMemo(() => partners.filter((partner) => {
    if (!partner.is_active) return false;
    if (paymentType === "customer_payment") return partner.partner_type === "customer" || partner.partner_type === "both";
    if (paymentType === "supplier_payment") return partner.partner_type === "supplier" || partner.partner_type === "both";
    return false;
  }), [partners, paymentType]);
  const selectedBalance = useMemo(
    () => balances.find((balance) => String(balance.partner_id) === partnerId),
    [balances, partnerId]
  );
  const allocatedAmount = useMemo(
    () => allocationInputs(allocations).reduce((total, allocation) => total + Number(allocation.amount), 0),
    [allocations]
  );
  const paymentAmount = Number(amount) || 0;
  const unallocatedAmount = paymentAmount - allocatedAmount;
  const allocationInvalid = allocatedAmount > paymentAmount;

  useEffect(() => {
    if (!canAllocate || !partnerId) {
      setAllocationOptions([]);
      return;
    }
    let active = true;
    api.paymentAllocationOptions(Number(partnerId), paymentType, allocatingPaymentId ?? undefined)
      .then((options) => {
        if (active) setAllocationOptions(options);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : t("apiLoadDocumentsError"));
      });
    return () => {
      active = false;
    };
  }, [allocatingPaymentId, canAllocate, partnerId, paymentType]);

  function setPaymentTypeChecked(nextType: string) {
    const currentPartner = partners.find((partner) => String(partner.id) === partnerId);
    const allowed =
      !currentPartner ||
      (nextType === "customer_payment" && ["customer", "both"].includes(currentPartner.partner_type)) ||
      (nextType === "supplier_payment" && ["supplier", "both"].includes(currentPartner.partner_type));
    setPaymentType(nextType);
    setAllocations({});
    if (!allowed) {
      setPartnerId("");
      setError(t("invalidPartnerForPayment"));
    }
  }

  function load() {
    Promise.all([api.payments(), api.partners(), api.partnerBalances()])
      .then(([paymentRows, partnerRows, balanceRows]) => {
        setRows(paymentRows);
        setPartners(partnerRows);
        setBalances(balanceRows);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiLoadPaymentsError")));
  }

  function resetForm() {
    setEditingId(null);
    setAllocatingPaymentId(null);
    setPartnerId("");
    setPaymentDate(new Date().toISOString().slice(0, 10));
    setPaymentType("customer_payment");
    setAmount("");
    setMethod("cash");
    setAllocations({});
    setAllocationOptions([]);
    setError("");
  }

  function fillFromPayment(row: Payment) {
    setPartnerId(String(row.partner_id));
    setPaymentDate(row.payment_date.slice(0, 10));
    setPaymentType(row.payment_type);
    setAmount(row.amount);
    setMethod(row.method ?? "cash");
    setAllocations(Object.fromEntries(row.allocations.map((allocation) => [allocation.document_id, allocation.amount])));
    setError("");
  }

  function edit(row: Payment) {
    if (row.status !== "draft") return;
    setEditingId(row.id);
    setAllocatingPaymentId(null);
    fillFromPayment(row);
  }

  function editAllocations(row: Payment) {
    if (row.status !== "posted" || !canAllocate) return;
    setEditingId(null);
    setAllocatingPaymentId(row.id);
    fillFromPayment(row);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function save() {
    if (!partnerId || !amount || allocationInvalid) return;
    const selectedAllocations = allocationInputs(allocations);
    if (isPostedAllocation && allocatingPaymentId) {
      api.replacePaymentAllocations(allocatingPaymentId, selectedAllocations)
        .then(() => {
          resetForm();
          load();
        })
        .catch((err) => setError(err instanceof Error ? err.message : t("apiAllocatePaymentError")));
      return;
    }
    const payload: PaymentWrite = {
      partner_id: Number(partnerId),
      payment_date: paymentDate,
      payment_type: paymentType,
      status: "draft",
      amount,
      method
    };
    if (canAllocate) payload.allocations = selectedAllocations;
    const request = editingId ? api.updatePayment(editingId, payload) : api.createPayment(payload);
    request
      .then(() => {
        resetForm();
        load();
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiCreatePaymentError")));
  }

  function distributeAutomatically() {
    let remainder = paymentAmount;
    const next: AllocationValues = {};
    for (const option of allocationOptions) {
      if (remainder <= 0) break;
      const allocation = Math.min(remainder, Number(option.outstanding_amount));
      if (allocation > 0) {
        next[option.document_id] = allocation.toFixed(2);
        remainder -= allocation;
      }
    }
    setAllocations(next);
  }

  function post(id: number) {
    api.postPayment(id).then(load).catch((err) => setError(err instanceof Error ? err.message : t("apiPostPaymentError")));
  }

  function cancel(id: number) {
    api.cancelPayment(id).then(load).catch((err) => setError(err instanceof Error ? err.message : t("apiCancelPaymentError")));
  }

  function removeDraft(id: number) {
    if (!window.confirm(t("deleteDraftConfirm"))) return;
    api.deletePayment(id).then(() => {
      if (editingId === id) resetForm();
      load();
    }).catch((err) => setError(err instanceof Error ? err.message : t("deleteError")));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <PageScaffold title={t("payments")}>
      <div className="panel payment-editor" style={{ marginBottom: 10 }}>
        {isPostedAllocation ? <div className="payment-editor-heading">{t("reallocatePostedPayment")} #{allocatingPaymentId}</div> : null}
        <div className="form-grid">
          <div className="field"><label>{t("date")}</label><input type="date" value={paymentDate} disabled={isPostedAllocation} onChange={(event) => setPaymentDate(event.target.value)} /></div>
          <div className="field">
            <label>{t("partner")}</label>
            <select
              data-testid="payment-partner"
              value={partnerId}
              disabled={isPostedAllocation}
              onChange={(event) => {
                setPartnerId(event.target.value);
                setAllocations({});
              }}
            >
              <option value="">{t("selectPartner")}</option>
              {partnerOptions.map((partner) => <option key={partner.id} value={partner.id}>{partner.name} - {formatCode(partner.partner_type, t)}</option>)}
            </select>
          </div>
          <div className="field">
            <label>{t("type")}</label>
            <select data-testid="payment-type" value={paymentType} disabled={isPostedAllocation} onChange={(event) => setPaymentTypeChecked(event.target.value)}>
              <option value="customer_payment">{t("customerPayment")}</option>
              <option value="supplier_payment">{t("supplierPayment")}</option>
            </select>
          </div>
          <div className="field">
            <label>{t("amount")}</label>
            <input data-testid="payment-amount" type="number" min="0.01" step="0.01" value={amount} disabled={isPostedAllocation} onChange={(event) => setAmount(event.target.value)} />
            {selectedBalance ? <small>{t("currentPartnerBalance")}: {formatMoney(selectedBalance.balance)}</small> : null}
          </div>
          <div className="field">
            <label>{t("method")}</label>
            <input value={formatCode(method, t)} disabled />
          </div>
          <div className="field">
            <label>&nbsp;</label>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className="button primary"
                title={!can(isPostedAllocation ? "payments.allocate" : editingId ? "payments.update" : "payments.create") ? t("noPermission") : ""}
                disabled={allocationInvalid || !can(isPostedAllocation ? "payments.allocate" : editingId ? "payments.update" : "payments.create")}
                data-testid="payment-save"
                onClick={save}
              >
                {isPostedAllocation ? t("saveAllocation") : editingId ? t("save") : t("createPayment")}
              </button>
              {(editingId || isPostedAllocation) ? <button className="button" onClick={resetForm}>{t("cancel")}</button> : null}
            </div>
          </div>
        </div>

        {canAllocate && partnerId ? (
          <section className="payment-allocation-section" aria-label={t("paymentAllocation")}>
            <div className="payment-allocation-toolbar">
              <div>
                <strong>{t("paymentAllocation")}</strong>
                <span>{t("paymentAllocationHint")}</span>
              </div>
              <div className="payment-allocation-actions">
                <button className="button" type="button" onClick={distributeAutomatically} disabled={paymentAmount <= 0}>{t("allocateOldestFirst")}</button>
                <button className="button" type="button" onClick={() => setAllocations({})}>{t("clearAllocation")}</button>
              </div>
            </div>
            <div className="payment-allocation-table-wrap">
              <table className="data-table payment-allocation-table">
                <thead>
                  <tr>
                    <th>{t("document")}</th>
                    <th>{t("date")}</th>
                    <th>{t("documentTotal")}</th>
                    <th>{t("alreadyPaid")}</th>
                    <th>{t("outstanding")}</th>
                    <th>{t("allocate")}</th>
                  </tr>
                </thead>
                <tbody>
                  {allocationOptions.map((option) => (
                    <tr key={option.document_id}>
                      <td>#{option.document_number || option.document_id}</td>
                      <td>{formatDate(option.document_date)}</td>
                      <td>{formatMoney(option.total_amount)}</td>
                      <td>{formatMoney(option.allocated_amount)}</td>
                      <td>{formatMoney(option.outstanding_amount)}</td>
                      <td>
                        <input
                          className="payment-allocation-input"
                          data-testid={`payment-allocation-${option.document_id}`}
                          type="number"
                          min="0"
                          max={option.outstanding_amount}
                          step="0.01"
                          value={allocations[option.document_id] ?? ""}
                          onChange={(event) => setAllocations((current) => ({ ...current, [option.document_id]: event.target.value }))}
                        />
                      </td>
                    </tr>
                  ))}
                  {allocationOptions.length === 0 ? <tr><td className="empty-cell" colSpan={6}>{t("noOutstandingDocuments")}</td></tr> : null}
                </tbody>
              </table>
            </div>
            <div className={`payment-allocation-summary${allocationInvalid ? " invalid" : ""}`}>
              <span>{t("paymentAmount")}: <b>{formatMoney(paymentAmount)}</b></span>
              <span>{t("allocated")}: <b>{formatMoney(allocatedAmount)}</b></span>
              <span>{t("unallocatedAdvance")}: <b>{formatMoney(unallocatedAmount)}</b></span>
              {allocationInvalid ? <strong>{t("allocationExceedsPayment")}</strong> : null}
            </div>
          </section>
        ) : null}
        {!canAllocate && partnerId ? <p className="muted-note payment-allocation-permission">{t("allocationManagerOnly")}</p> : null}
      </div>
      {error ? <p className="panel error-panel">{error}</p> : null}
      <DataTable<Payment>
        rows={rows}
        emptyMessage={t("noPayments")}
        searchable
        columns={[
          { key: "payment_date", header: t("date"), sortable: true, render: (row) => formatDate(row.payment_date) },
          { key: "partner_name", header: t("partner"), sortable: true },
          { key: "document_number", header: t("documents"), sortable: true },
          { key: "payment_type", header: t("type"), sortable: true, render: (row) => formatCode(row.payment_type, t) },
          { key: "amount", header: t("amount"), sortable: true, render: (row) => formatMoney(row.amount) },
          { key: "allocated_amount", header: t("allocated"), sortable: true, render: (row) => formatMoney(row.allocated_amount) },
          { key: "unallocated_amount", header: t("advance"), sortable: true, render: (row) => formatMoney(row.unallocated_amount) },
          { key: "method", header: t("method"), sortable: true, render: (row) => formatCode(row.method, t) },
          { key: "status", header: t("status"), sortable: true, render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          {
            key: "cash_operation_status",
            header: t("cash"),
            render: (row) => row.cash_operation_id ? `#${row.cash_operation_id} ${formatCode(row.cash_operation_status, t)}` : ""
          },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
                <button className="button" title={!can("payments.update") ? t("noPermission") : ""} disabled={row.status !== "draft" || !can("payments.update")} onClick={() => edit(row)}>{t("edit")}</button>
                <button data-testid={`payment-post-${row.id}`} className="button" title={!can("payments.post") ? t("noPermission") : ""} disabled={row.status !== "draft" || !can("payments.post")} onClick={() => post(row.id)}>{t("post")}</button>
                <button className="button" title={!canAllocate ? t("noPermission") : ""} disabled={row.status !== "posted" || row.payment_type === "refund" || !canAllocate} onClick={() => editAllocations(row)}>{t("allocate")}</button>
                <button className="button" title={!can("payments.cancel") ? t("noPermission") : ""} disabled={row.status !== "posted" || !can("payments.cancel")} onClick={() => cancel(row.id)}>{t("cancel")}</button>
                <button className="button" title={!can("payments.delete") ? t("noPermission") : ""} disabled={row.status !== "draft" || !can("payments.delete")} onClick={() => removeDraft(row.id)}>{t("deleteDraft")}</button>
              </div>
            )
          }
        ]}
      />
    </PageScaffold>
  );
}
