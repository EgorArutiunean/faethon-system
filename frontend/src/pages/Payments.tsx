import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth";
import { DataTable } from "../components/DataTable";
import { JournalViews } from "../components/JournalViews";
import { useConfirmDialog } from "../components/ConfirmDialog";
import { PageScaffold } from "../components/PageScaffold";
import { DraftRecoveryNotice } from "../components/DraftRecoveryNotice";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useLocalDraft } from "../hooks/useLocalDraft";
import {
  DocumentPaymentSummary,
  Partner,
  PartnerBalance,
  Payment,
  PaymentAllocationInput,
  PaymentAllocationOption,
  PaymentWrite,
  api
} from "../lib/api";
import { JournalConfig, useJournalState } from "../lib/journalState";

type AllocationValues = Record<number, string>;
type PaymentForm = {
  editorOpen: boolean;
  partnerId: string;
  partnerSearch: string;
  paymentDate: string;
  paymentType: string;
  amount: string;
  method: string;
  allocations: AllocationValues;
};
const PAGE_SIZE = 25;
type PaymentSort = "payment_date" | "id" | "amount" | "status";
const JOURNAL_CONFIG: JournalConfig<PaymentSort> = {
  id: "payments", defaultSort: "payment_date", sorts: ["payment_date", "id", "amount", "status"],
  types: ["customer_payment", "supplier_payment", "refund"],
};

function allocationInputs(values: AllocationValues): PaymentAllocationInput[] {
  return Object.entries(values)
    .map(([documentId, value]) => ({ document_id: Number(documentId), amount: value }))
    .filter((allocation) => Number(allocation.amount) > 0);
}

function positiveId(value: string | null) {
  return value && /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : null;
}

function emptyPaymentForm(open = false, type = "customer_payment"): PaymentForm {
  return { editorOpen: open, partnerId: "", partnerSearch: "", paymentDate: new Date().toISOString().slice(0, 10), paymentType: type, amount: "", method: "cash", allocations: {} };
}

function formFromPayment(row: Payment): PaymentForm {
  return { editorOpen: true, partnerId: String(row.partner_id), partnerSearch: "", paymentDate: row.payment_date.slice(0, 10), paymentType: row.payment_type, amount: row.amount, method: row.method ?? "cash", allocations: Object.fromEntries(row.allocations.map((allocation) => [allocation.document_id, allocation.amount])) };
}

function validPaymentForm(value: unknown): value is PaymentForm {
  if (!value || typeof value !== "object") return false;
  const form = value as Partial<PaymentForm>;
  return typeof form.editorOpen === "boolean" && typeof form.partnerId === "string" && (form.partnerId === "" || positiveId(form.partnerId) !== null)
    && typeof form.partnerSearch === "string" && form.partnerSearch.length <= 500
    && typeof form.paymentDate === "string" && form.paymentDate.length <= 10
    && typeof form.paymentType === "string" && ["customer_payment", "supplier_payment"].includes(form.paymentType)
    && typeof form.amount === "string" && form.amount.length <= 100 && form.method === "cash"
    && !!form.allocations && typeof form.allocations === "object" && !Array.isArray(form.allocations)
    && Object.entries(form.allocations).every(([id, amount]) => positiveId(id) !== null && typeof amount === "string" && amount.length <= 100);
}

export function Payments() {
  const { t } = useI18n();
  const { can } = useAuth();
  const { ask, dialog } = useConfirmDialog();
  const [searchParams, setSearchParams] = useSearchParams();
  const documentFilterId = positiveId(searchParams.get("document_id"));
  const requestedEditId = positiveId(searchParams.get("edit_payment"));
  const requestedAllocationId = positiveId(searchParams.get("allocate_payment"));
  const requestedCreate = searchParams.get("create");
  const createIdentity = requestedCreate === "customer_payment" || requestedCreate === "supplier_payment" ? `new:${requestedCreate}` : "new";
  const editorIdentity = requestedAllocationId ? `allocate:${requestedAllocationId}` : requestedEditId ? `edit:${requestedEditId}` : documentFilterId ? `document:${documentFilterId}` : createIdentity;
  const [rows, setRows] = useState<Payment[]>([]);
  const [total, setTotal] = useState(0);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const journal = useJournalState(JOURNAL_CONFIG);
  const { page, search: journalSearch, dateFrom, statusFilter, typeFilter, sortBy, sortOrder } = journal.state;
  const loadRequest = useRef(0);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [balances, setBalances] = useState<PartnerBalance[]>([]);
  const [allocationOptions, setAllocationOptions] = useState<PaymentAllocationOption[]>([]);
  const [allocations, setAllocations] = useState<AllocationValues>({});
  const [partnerId, setPartnerId] = useState("");
  const [partnerSearch, setPartnerSearch] = useState("");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [paymentType, setPaymentType] = useState("customer_payment");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [allocatingPaymentId, setAllocatingPaymentId] = useState<number | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [preparedIdentity, setPreparedIdentity] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<PaymentForm>(() => emptyPaymentForm());
  const [serverRevision, setServerRevision] = useState("new");
  const [contextSummary, setContextSummary] = useState<DocumentPaymentSummary | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const mountedRef = useRef(true);
  const editorContext = JSON.stringify([editorIdentity, documentFilterId, requestedCreate]);
  const currentContext = useRef({ signature: editorContext });
  if (currentContext.current.signature !== editorContext) currentContext.current = { signature: editorContext };

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

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
  const isDocumentCreation = documentFilterId !== null && !editingId && !isPostedAllocation && editorOpen;
  const formValue: PaymentForm = { editorOpen, partnerId, partnerSearch, paymentDate, paymentType, amount, method, allocations };

  function applyForm(value: PaymentForm) {
    setEditorOpen(value.editorOpen);
    setPartnerId(value.partnerId);
    setPartnerSearch(value.partnerSearch);
    setPaymentDate(value.paymentDate);
    setPaymentType(value.paymentType);
    setAmount(value.amount);
    setMethod(value.method);
    setAllocations(value.allocations);
    if (value.partnerId) api.partner(Number(value.partnerId)).then((partner) => {
      setPartners((current) => current.some((item) => item.id === partner.id) ? current : [partner, ...current]);
    }).catch(() => undefined);
  }

  const draft = useLocalDraft<PaymentForm>({
    scope: "payment", entityId: editorIdentity, revision: serverRevision, value: formValue,
    dirty: editorOpen && JSON.stringify(formValue) !== JSON.stringify(baseline),
    enabled: preparedIdentity === editorIdentity && (requestedEditId ? can("payments.update") : requestedAllocationId ? canAllocate : can("payments.create")),
    validate: validPaymentForm, onRestore: applyForm, onDiscard: () => applyForm(baseline),
  });

  useEffect(() => {
    let active = true;
    setPreparedIdentity(null);
    setContextSummary(null);
    setError("");
    setEditorOpen(false);
    setEditingId(requestedEditId);
    setAllocatingPaymentId(requestedAllocationId);
    const invalidQuery = (searchParams.has("document_id") && !documentFilterId)
      || (searchParams.has("edit_payment") && !requestedEditId)
      || (searchParams.has("allocate_payment") && !requestedAllocationId)
      || (requestedEditId !== null && requestedAllocationId !== null);
    if (invalidQuery) {
      setError(t("documentPaymentContextInvalid"));
      return;
    }
    async function prepare() {
      const paymentId = requestedAllocationId ?? requestedEditId;
      if (paymentId) {
        const row = await api.payment(paymentId);
        if (!active) return;
        if ((requestedAllocationId && (row.status !== "posted" || !canAllocate)) || (requestedEditId && (row.status !== "draft" || !can("payments.update")))) throw new Error(t("documentPaymentContextInvalid"));
        const options = requestedAllocationId ? await api.paymentAllocationOptions(row.partner_id, row.payment_type, row.id) : null;
        if (!active) return;
        if (options) setAllocationOptions(options);
        const next = formFromPayment(row);
        setBaseline(next);
        applyForm(next);
        setServerRevision(JSON.stringify([row.updated_at, next, options?.map((option) => [option.document_id, option.outstanding_amount])]));
      } else if (documentFilterId) {
        setContextLoading(true);
        const summary = await api.documentPaymentSummary(documentFilterId);
        if (!active) return;
        setContextSummary(summary);
        const eligible = summary.document_status === "posted" && summary.partner_id !== null && summary.payment_type !== null && Number(summary.outstanding_amount) > 0;
        if (requestedCreate && (!eligible || !can("payments.create") || !canAllocate || requestedCreate !== summary.payment_type)) throw new Error(t("documentPaymentContextInvalid"));
        const next: PaymentForm = eligible ? {
          ...emptyPaymentForm(Boolean(requestedCreate), summary.payment_type!),
          partnerId: String(summary.partner_id), amount: summary.outstanding_amount,
          allocations: { [documentFilterId]: summary.outstanding_amount },
        } : emptyPaymentForm();
        setBaseline(next);
        applyForm(next);
        setServerRevision(JSON.stringify([summary.document_status, summary.partner_id, summary.payment_type, summary.total_amount, summary.outstanding_amount]));
      } else {
        const next = emptyPaymentForm(Boolean(requestedCreate), requestedCreate === "supplier_payment" ? "supplier_payment" : "customer_payment");
        setBaseline(next);
        applyForm(next);
        setServerRevision("new");
      }
      if (active) setPreparedIdentity(editorIdentity);
    }
    prepare().catch((err) => {
      if (active) setError(err instanceof Error ? err.message : t("documentPaymentContextInvalid"));
    }).finally(() => active && setContextLoading(false));
    return () => { active = false; };
  }, [documentFilterId, requestedAllocationId, requestedEditId, requestedCreate, editorIdentity]);

  useEffect(() => {
    if (!documentFilterId || editorOpen || refreshVersion === 0) return;
    let active = true;
    api.documentPaymentSummary(documentFilterId)
      .then((summary) => active && setContextSummary(summary))
      .catch((err) => active && setError(err instanceof Error ? err.message : t("relatedOperationsLoadError")));
    return () => { active = false; };
  }, [documentFilterId, editorOpen, refreshVersion]);

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

  useEffect(() => {
    let active = true;
    const timeout = window.setTimeout(() => {
      const role = paymentType === "supplier_payment" ? "supplier" : "customer";
      api.partnerOptions(partnerSearch, role)
        .then((items) => {
          if (!active) return;
          setPartners((current) => {
            const selected = current.find((item) => String(item.id) === partnerId);
            return selected && !items.some((item) => item.id === selected.id) ? [selected, ...items] : items;
          });
        })
        .catch(() => active && setPartners([]));
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [partnerSearch, paymentType]);

  useEffect(() => {
    if (!partnerId) {
      setBalances([]);
      return;
    }
    api.partnerBalance(Number(partnerId)).then((balance) => setBalances([balance])).catch(() => setBalances([]));
  }, [partnerId]);

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
    const requestId = ++loadRequest.current;
    api.paymentPage({ offset: page * PAGE_SIZE, limit: PAGE_SIZE, search: journalSearch, date_from: dateFrom, status: statusFilter, payment_type: typeFilter, sort_by: sortBy, sort_order: sortOrder, document_id: documentFilterId ?? undefined })
      .then((result) => {
        if (requestId !== loadRequest.current) return;
        if (result.total === 0 && page > 0) {
          journal.update({ page: 0 });
          return;
        }
        if (result.total > 0 && page * PAGE_SIZE >= result.total) {
          journal.update({ page: Math.max(0, Math.ceil(result.total / PAGE_SIZE) - 1) });
          return;
        }
        setRows(result.items);
        setTotal(result.total);
        journal.markLoaded();
      })
      .catch((err) => {
        if (requestId === loadRequest.current) setError(err instanceof Error ? err.message : t("apiLoadPaymentsError"));
      });
  }

  function refreshJournal() {
    setRefreshVersion((current) => current + 1);
  }

  function resetForm() {
    draft.clear();
    applyForm(emptyPaymentForm());
    setAllocationOptions([]);
    setError("");
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("create");
      next.delete("edit_payment");
      next.delete("allocate_payment");
      return next;
    }, { replace: true, preventScrollReset: true });
  }

  function openEditorQuery(key: "create" | "edit_payment" | "allocate_payment", value: string) {
    const next = new URLSearchParams(searchParams);
    next.delete("create");
    next.delete("edit_payment");
    next.delete("allocate_payment");
    next.set(key, value);
    setSearchParams(next, { replace: true, preventScrollReset: true });
  }

  function createNew() {
    if (savingRef.current || !can("payments.create")) return;
    if (documentFilterId && (!contextSummary?.payment_type || !canAllocate || Number(contextSummary.outstanding_amount) <= 0 || contextSummary.document_status !== "posted")) {
      setError(t("documentPaymentUnavailable"));
      return;
    }
    openEditorQuery("create", documentFilterId ? contextSummary!.payment_type! : "customer_payment");
  }

  function edit(row: Payment) {
    if (savingRef.current || row.status !== "draft" || !can("payments.update")) return;
    openEditorQuery("edit_payment", String(row.id));
  }

  function editAllocations(row: Payment) {
    if (savingRef.current || row.status !== "posted" || !canAllocate) return;
    openEditorQuery("allocate_payment", String(row.id));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function save() {
    if (savingRef.current || preparedIdentity !== editorIdentity) return;
    if (!partnerId) {
      setError(t("selectPartner"));
      return;
    }
    if (!paymentDate) {
      setError(t("selectDate"));
      return;
    }
    if (!Number.isFinite(Number(amount)) || Number(amount) <= 0) {
      setError(t("amountPositive"));
      return;
    }
    if (allocationInvalid) {
      setError(t("allocationExceedsPayment"));
      return;
    }
    if (isDocumentCreation && (!contextSummary || partnerId !== String(contextSummary.partner_id) || paymentType !== contextSummary.payment_type || !canAllocate || !(Number(allocations[contextSummary.document_id]) > 0))) {
      setError(t("documentPaymentContextInvalid"));
      return;
    }
    setError("");
    savingRef.current = true;
    setSaving(true);
    const savingContext = currentContext.current;
    const isCurrentContext = () => mountedRef.current && currentContext.current === savingContext;
    const completeSave = () => {
      draft.clear();
      if (isCurrentContext()) resetForm();
      if (mountedRef.current) refreshJournal();
    };
    const finishSave = () => {
      savingRef.current = false;
      if (mountedRef.current) setSaving(false);
    };
    const selectedAllocations = allocationInputs(allocations);
    if (isPostedAllocation && allocatingPaymentId) {
      api.replacePaymentAllocations(allocatingPaymentId, selectedAllocations)
        .then(completeSave)
        .catch((err) => { if (isCurrentContext()) setError(err instanceof Error ? err.message : t("apiAllocatePaymentError")); })
        .finally(finishSave);
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
      .then(completeSave)
      .catch((err) => { if (isCurrentContext()) setError(err instanceof Error ? err.message : t("apiCreatePaymentError")); })
      .finally(finishSave);
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

  async function post(id: number) {
    if (savingRef.current) return;
    if (!(await ask({ message: t("postPaymentConfirm").replace("{id}", String(id)), confirmLabel: t("post") }))) return;
    api.postPayment(id).then(refreshJournal).catch((err) => setError(err instanceof Error ? err.message : t("apiPostPaymentError")));
  }

  async function cancel(id: number) {
    if (savingRef.current) return;
    if (!(await ask({ message: t("cancelPaymentConfirm").replace("{id}", String(id)), confirmLabel: t("cancel"), danger: true }))) return;
    api.cancelPayment(id).then(refreshJournal).catch((err) => setError(err instanceof Error ? err.message : t("apiCancelPaymentError")));
  }

  async function removeDraft(id: number) {
    if (savingRef.current) return;
    if (!(await ask({ message: `${t("deleteDraftConfirm")} #${id}`, confirmLabel: t("deleteDraft"), danger: true }))) return;
    api.deletePayment(id).then(() => {
      if (editingId === id) resetForm();
      refreshJournal();
    }).catch((err) => setError(err instanceof Error ? err.message : t("deleteError")));
  }

  useEffect(() => {
    const timeout = window.setTimeout(load, 250);
    return () => {
      window.clearTimeout(timeout);
      loadRequest.current += 1;
    };
  }, [dateFrom, page, journalSearch, statusFilter, typeFilter, sortBy, sortOrder, refreshVersion, documentFilterId]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <PageScaffold title={t("payments")}>
      {dialog}
      <div className="workspace-command-bar">
        <button className="button primary" disabled={!can("payments.create") || contextLoading || saving} onClick={createNew} aria-expanded={editorOpen}>
          {t("createPayment")}
        </button>
        <span>{t("payments")}: {total}</span>
      </div>
      {documentFilterId ? <div className="panel payment-document-context" aria-label={t("documentPaymentContext")}>
        <Link to={`/documents/${documentFilterId}`}>{t("document")} {contextSummary?.document_number || `#${documentFilterId}`}</Link>
        {contextSummary ? <span>{t("documentOutstanding")}: {formatMoney(contextSummary.outstanding_amount)}</span> : null}
        <Link className="button" to="/payments?page=1">{t("clearDocumentPaymentFilter")}</Link>
      </div> : null}
      {contextLoading ? <p role="status">{t("documentPaymentContextLoading")}</p> : null}
      <fieldset disabled={saving} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}><DraftRecoveryNotice draft={draft} /></fieldset>
      {editorOpen ? (
      <div className="panel payment-editor" style={{ marginBottom: 10 }}>
        {isPostedAllocation ? <div className="payment-editor-heading">{t("reallocatePostedPayment")} #{allocatingPaymentId}</div> : null}
        <div className="form-grid">
          <div className="field"><label htmlFor="payment-date">{t("date")}</label><input id="payment-date" type="date" value={paymentDate} disabled={isPostedAllocation || saving} onChange={(event) => setPaymentDate(event.target.value)} /></div>
          <div className="field"><label>{t("search")}: {t("partner")}</label><input value={partnerSearch} onChange={(event) => setPartnerSearch(event.target.value)} disabled={isPostedAllocation || isDocumentCreation || saving} /></div>
          <div className="field">
            <label htmlFor="payment-partner">{t("partner")}</label>
            <select
              id="payment-partner"
              data-testid="payment-partner"
              value={partnerId}
              disabled={isPostedAllocation || isDocumentCreation || saving}
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
            <select data-testid="payment-type" value={paymentType} disabled={isPostedAllocation || isDocumentCreation || saving} onChange={(event) => setPaymentTypeChecked(event.target.value)}>
              <option value="customer_payment">{t("customerPayment")}</option>
              <option value="supplier_payment">{t("supplierPayment")}</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="payment-amount">{t("amount")}</label>
            <input id="payment-amount" data-testid="payment-amount" type="number" min="0.01" step="0.01" value={amount} disabled={isPostedAllocation || saving} onChange={(event) => {
              setAmount(event.target.value);
              if (isDocumentCreation && contextSummary) {
                const allocated = Math.min(Math.max(Number(event.target.value) || 0, 0), Number(contextSummary.outstanding_amount));
                setAllocations({ [contextSummary.document_id]: allocated > 0 ? allocated.toFixed(2) : "" });
              }
            }} />
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
                disabled={saving || preparedIdentity !== editorIdentity || allocationInvalid || !can(isPostedAllocation ? "payments.allocate" : editingId ? "payments.update" : "payments.create")}
                data-testid="payment-save"
                onClick={save}
              >
                {isPostedAllocation ? t("saveAllocation") : editingId ? t("save") : t("createPayment")}
              </button>
              <button className="button" disabled={saving} onClick={resetForm}>{t("cancel")}</button>
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
              {!isDocumentCreation ? <div className="payment-allocation-actions">
                <button className="button" type="button" onClick={distributeAutomatically} disabled={paymentAmount <= 0 || saving}>{t("allocateOldestFirst")}</button>
                <button className="button" type="button" disabled={saving} onClick={() => setAllocations({})}>{t("clearAllocation")}</button>
              </div> : null}
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
                  {allocationOptions.filter((option) => !isDocumentCreation || option.document_id === documentFilterId).map((option) => (
                    <tr key={option.document_id}>
                      <td data-label={t("document")}>#{option.document_number || option.document_id}</td>
                      <td data-label={t("date")}>{formatDate(option.document_date)}</td>
                      <td data-label={t("documentTotal")}>{formatMoney(option.total_amount)}</td>
                      <td data-label={t("alreadyPaid")}>{formatMoney(option.allocated_amount)}</td>
                      <td data-label={t("outstanding")}>{formatMoney(option.outstanding_amount)}</td>
                      <td data-label={t("allocate")}>
                        <input
                          className="payment-allocation-input"
                          data-testid={`payment-allocation-${option.document_id}`}
                          type="number"
                          min="0"
                          max={option.outstanding_amount}
                          step="0.01"
                          value={allocations[option.document_id] ?? ""}
                          disabled={saving}
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
      ) : null}
      {error ? <p className="panel error-panel">{error}</p> : null}
      <div className="panel"><JournalViews {...journal} /></div>
      <div className="panel toolbar journal-toolbar">
        <input className="search" aria-label={t("search")} value={journalSearch} onChange={(event) => journal.update({ search: event.target.value, page: 0 })} placeholder={t("search")} />
        <label className="journal-date-filter">С даты <input type="date" value={dateFrom} onChange={(event) => journal.update({ dateFrom: event.target.value, page: 0 })} /></label>
        <select aria-label={`${t("filter")}: ${t("status")}`} value={statusFilter} onChange={(event) => journal.update({ statusFilter: event.target.value, page: 0 })}>
          <option value="">{t("all")}: {t("status")}</option><option value="draft">{t("draft")}</option><option value="posted">{t("posted")}</option><option value="cancelled">{t("cancelled")}</option>
        </select>
        <select aria-label={`${t("filter")}: ${t("type")}`} value={typeFilter} onChange={(event) => journal.update({ typeFilter: event.target.value, page: 0 })}>
          <option value="">{t("all")}: {t("type")}</option><option value="customer_payment">{t("customerPayment")}</option><option value="supplier_payment">{t("supplierPayment")}</option><option value="refund">{t("refund")}</option>
        </select>
        <select aria-label={t("sortBy")} value={sortBy} onChange={(event) => journal.update({ sortBy: event.target.value as PaymentSort, page: 0 })}>
          <option value="payment_date">{t("date")}</option><option value="id">ID</option><option value="amount">{t("amount")}</option><option value="status">{t("status")}</option>
        </select>
        <button className="button" aria-label={t("sortDirection")} onClick={() => journal.update({ sortOrder: sortOrder === "asc" ? "desc" : "asc", page: 0 })}>{sortOrder === "asc" ? "↑" : "↓"}</button>
        {journalSearch || dateFrom || statusFilter || typeFilter || sortBy !== "payment_date" || sortOrder !== "desc" ? <button className="button" onClick={journal.reset}>{t("resetFilters")}</button> : null}
      </div>
      <DataTable<Payment>
        rows={rows}
        emptyMessage={t("noPayments")}
        pageSize={PAGE_SIZE}
        columns={[
          { key: "payment_date", header: t("date"), render: (row) => formatDate(row.payment_date) },
          { key: "partner_name", header: t("partner") },
          { key: "document_number", header: t("documents") },
          { key: "payment_type", header: t("type"), render: (row) => formatCode(row.payment_type, t) },
          { key: "amount", header: t("amount"), render: (row) => formatMoney(row.amount) },
          { key: "allocated_amount", header: t("allocated"), render: (row) => formatMoney(row.allocated_amount) },
          { key: "unallocated_amount", header: t("advance"), render: (row) => formatMoney(row.unallocated_amount) },
          { key: "method", header: t("method"), render: (row) => formatCode(row.method, t) },
          { key: "status", header: t("status"), render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          {
            key: "cash_operation_status",
            header: t("cash"),
            render: (row) => row.cash_operation_id ? `#${row.cash_operation_id} ${formatCode(row.cash_operation_status, t)}` : ""
          },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div className="payment-row-actions">
                {row.status === "draft" && can("payments.update") ? <button className="button" disabled={saving} onClick={() => edit(row)}>{t("edit")}</button> : null}
                {row.status === "draft" && can("payments.post") ? <button data-testid={`payment-post-${row.id}`} className="button primary" disabled={saving} onClick={() => post(row.id)}>{t("post")}</button> : null}
                {row.status === "posted" && row.payment_type !== "refund" && canAllocate ? <button className="button" disabled={saving} onClick={() => editAllocations(row)}>{t("allocate")}</button> : null}
                {(row.status === "posted" && can("payments.cancel")) || (row.status === "draft" && can("payments.delete")) ? <details className="row-more-actions"><summary className="button">{t("moreActions")}</summary><div>
                  {row.status === "posted" && can("payments.cancel") ? <button className="button" disabled={saving} onClick={() => cancel(row.id)}>{t("cancel")}</button> : null}
                  {row.status === "draft" && can("payments.delete") ? <button className="button" disabled={saving} onClick={() => removeDraft(row.id)}>{t("deleteDraft")}</button> : null}
                </div></details> : null}
              </div>
            )
          }
        ]}
      />
      {pageCount > 1 ? <div className="panel table-footer"><span>{page + 1} / {pageCount} · {t("total")}: {total}</span><span><button className="button" disabled={page === 0} onClick={() => journal.update({ page: Math.max(0, page - 1) })}>‹</button><button className="button" disabled={page >= pageCount - 1} onClick={() => journal.update({ page: Math.min(pageCount - 1, page + 1) })}>›</button></span></div> : null}
    </PageScaffold>
  );
}
