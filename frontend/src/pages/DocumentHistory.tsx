import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { DataTable } from "../components/DataTable";
import { historyApi, HistoryDetail, HistoryItem, HistoryPage } from "../lib/api";

const kind = (v: string) => v === "incoming" ? "Приходная" : "Расходная";
const currency = (code: string) => ({ "1": "руб. ПМР", "2": "MDL", "3": "USD", "4": "RUB", "5": "UAH", "7": "EUR" }[code] ?? `Валюта ${code}`);
const amount = (v: string | undefined, digits = 3) => v == null || v === "<null>" ? "—" : new Intl.NumberFormat("ru-RU", { maximumFractionDigits: digits }).format(Number(v));
const day = (v: string) => v.split("-").reverse().join(".");
const note = "Архив старой базы. Только просмотр. Эти накладные уже учтены в перенесённых остатках и не участвуют в расчёте текущих долгов.";

export function DocumentHistory() {
  const { can } = useAuth();
  const allowed = can("documents.read");
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<HistoryPage | null>(null);
  const [error, setError] = useState("");
  const search = params.get("search") ?? "";
  const type = params.get("document_type") ?? "";
  const from = params.get("date_from") ?? "";
  const to = params.get("date_to") ?? "";
  const page = Math.max(0, Number(params.get("page")) || 0);
  useEffect(() => {
    if (!allowed) return;
    let active = true; setData(null); setError("");
    const query = new URLSearchParams({ offset: String(page * 25), limit: "25" });
    for (const [key, value] of Object.entries({ search, document_type: type, date_from: from, date_to: to })) if (value) query.set(key, value);
    historyApi.list(query).then(result => { if (active) setData(result); }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [allowed, page, search, type, from, to]);
  function filter(key: string, value: string) { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); next.delete("page"); setParams(next, { replace: true }); }
  function navigatePage(nextPage: number) { const next = new URLSearchParams(params); next.set("page", String(nextPage)); setParams(next); }
  if (!allowed) return <p role="alert">Нет доступа к накладным.</p>;
  return <section>
    <Link to="/documents">К рабочим накладным</Link>
    <h1>История накладных</h1><p>{note}</p>
    <div className="toolbar">
      <label>Номер или контрагент <input value={search} onChange={e => filter("search", e.target.value)} /></label>
      <label>Тип <select value={type} onChange={e => filter("document_type", e.target.value)}><option value="">Все</option><option value="incoming">Приходные</option><option value="outgoing">Расходные</option></select></label>
      <label>С <input type="date" value={from} onChange={e => filter("date_from", e.target.value)} /></label>
      <label>По <input type="date" value={to} onChange={e => filter("date_to", e.target.value)} /></label>
    </div>
    {error ? <p role="alert">{error}</p> : !data ? <p role="status">Загрузка…</p> : <>
      <p>Найдено: {data.total}</p>
      <DataTable<HistoryItem> rows={data.items} pageSize={25} emptyMessage="Исторические накладные не найдены" columns={[
        { key: "number", header: "Номер", render: r => <Link to={`/document-history/${r.id}`}>{r.header.number}</Link> },
        { key: "date", header: "Дата", render: r => day(r.header.date) },
        { key: "type", header: "Тип", render: r => kind(r.header.type) },
        { key: "partner", header: "Контрагент", render: r => `${r.header.partner_name} (${r.header.partner_code})` },
        { key: "warehouse", header: "Склад", render: r => r.header.warehouse_code },
        { key: "amount", header: "Сумма", render: r => `${amount(r.header.amount)} ${currency(r.header.currency_code)}` },
        { key: "lines", header: "Строк", render: r => r.header.line_count }
      ]} />
      <div className="toolbar"><button className="button" disabled={page === 0} onClick={() => navigatePage(page-1)}>Назад</button><span>Страница {page+1}</span><button className="button" disabled={(page+1)*25 >= data.total} onClick={() => navigatePage(page+1)}>Далее</button></div>
    </>}
  </section>;
}

export function DocumentHistoryDetail() {
  const { id } = useParams(); const { can } = useAuth(); const allowed = can("documents.read");
  const [data, setData] = useState<HistoryDetail | null>(null); const [error, setError] = useState("");
  useEffect(() => { if (!allowed || !id) return; let active = true; setData(null); setError(""); historyApi.detail(id).then(r => { if (active) setData(r); }).catch(e => { if (active) setError(String(e)); }); return () => { active = false; }; }, [allowed, id]);
  if (!allowed) return <p role="alert">Нет доступа к накладным.</p>;
  const h = data?.header;
  return <section><Link to="/document-history">К истории накладных</Link>
    {error ? <p role="alert">{error}</p> : !data || !h ? <p role="status">Загрузка…</p> : <>
      <h1>{kind(h.type)} № {h.number} от {day(h.date)}</h1><p>{note}</p>
      <dl><dt>Контрагент</dt><dd>{h.partner_name} ({h.partner_code})</dd><dt>Склад</dt><dd>{h.warehouse_code}</dd>
        <dt>Сумма документа</dt><dd>{amount(h.amount)} {currency(h.currency_code)}</dd><dt>Скидка в источнике</dt><dd>{amount(h.discount_amount)} {currency(h.currency_code)}</dd>
        <dt>Долг на дату старой копии (справочно)</dt><dd>{amount(h.source.DOLG_)} {currency(h.currency_code)}</dd>
        <dt>Исходный код статуса</dt><dd>{h.source_status}</dd></dl>
      <DataTable rows={data.lines} pageSize={100} columns={[
        { key: "line_number", header: "Строка" }, { key: "product_code", header: "Код товара" }, { key: "product_name", header: "Товар" },
        { key: "unit_name", header: "Ед. изм." }, { key: "quantity", header: "Количество", render: r => amount(r.quantity,6) },
        { key: "price", header: `Цена, ${currency(h.currency_code)}`, render: r => amount(r.price,6) },
        { key: "amount", header: `Сумма, ${currency(h.currency_code)}`, render: r => amount(r.amount,6) }
      ]} />
      <details><summary>Исходные реквизиты и значения</summary><p>Значения сохранены из старой базы. Код статуса не переименован в «проведён».</p><pre style={{ overflowX: "auto", maxHeight: 500 }}>{JSON.stringify({ header: h.source, lines: data.lines.map(l => ({ code: l.product_code, source: l.source })) }, null, 2)}</pre></details>
    </>}
  </section>;
}
