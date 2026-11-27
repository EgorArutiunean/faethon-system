import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../auth";

export type JournalState<Sort extends string = string> = {
  search: string;
  dateFrom: string;
  typeFilter: string;
  statusFilter: string;
  sortBy: Sort;
  sortOrder: "asc" | "desc";
  page: number;
};

export type JournalConfig<Sort extends string> = {
  id: "documents" | "payments";
  defaultSort: Sort;
  sorts: readonly Sort[];
  types: readonly string[];
};

export type JournalView<Sort extends string = string> = {
  id: string;
  name: string;
  state: JournalState<Sort>;
};

const queryKeys = ["q", "date_from", "type", "status", "sort", "order", "page"];
const statuses = ["draft", "posted", "cancelled"];

function defaults<Sort extends string>(config: JournalConfig<Sort>): JournalState<Sort> {
  return { search: "", dateFrom: "", typeFilter: "", statusFilter: "", sortBy: config.defaultSort, sortOrder: "desc", page: 0 };
}

function normalize<Sort extends string>(value: Partial<JournalState>, config: JournalConfig<Sort>): JournalState<Sort> {
  const result = defaults(config);
  if (typeof value.search === "string") result.search = value.search.slice(0, 200);
  if (typeof value.dateFrom === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value.dateFrom) && !Number.isNaN(Date.parse(value.dateFrom)) && new Date(value.dateFrom).toISOString().slice(0, 10) === value.dateFrom) result.dateFrom = value.dateFrom;
  if (typeof value.typeFilter === "string" && config.types.includes(value.typeFilter)) result.typeFilter = value.typeFilter;
  if (typeof value.statusFilter === "string" && statuses.includes(value.statusFilter)) result.statusFilter = value.statusFilter;
  if (config.sorts.includes(value.sortBy as Sort)) result.sortBy = value.sortBy as Sort;
  if (value.sortOrder === "asc") result.sortOrder = "asc";
  if (Number.isSafeInteger(value.page) && Number(value.page) >= 0 && Number(value.page) < 1_000_000) result.page = Number(value.page);
  return result;
}

function fromQuery<Sort extends string>(params: URLSearchParams, config: JournalConfig<Sort>) {
  return normalize({
    search: params.get("q") ?? "",
    dateFrom: params.get("date_from") ?? "",
    typeFilter: params.get("type") ?? "",
    statusFilter: params.get("status") ?? "",
    sortBy: params.get("sort") ?? "",
    sortOrder: params.get("order") as "asc" | "desc",
    page: Number(params.get("page") ?? "1") - 1,
  }, config);
}

function toQuery<Sort extends string>(params: URLSearchParams, state: JournalState<Sort>, config: JournalConfig<Sort>) {
  const next = new URLSearchParams(params);
  queryKeys.forEach((key) => next.delete(key));
  if (state.search) next.set("q", state.search);
  if (state.dateFrom) next.set("date_from", state.dateFrom);
  if (state.typeFilter) next.set("type", state.typeFilter);
  if (state.statusFilter) next.set("status", state.statusFilter);
  if (state.sortBy !== config.defaultSort) next.set("sort", state.sortBy);
  if (state.sortOrder !== "desc") next.set("order", state.sortOrder);
  // An explicit first page distinguishes a reset list from a link that should resume the last list.
  next.set("page", String(state.page + 1));
  return next;
}

function readJson(storage: Storage, key: string): unknown {
  try { return JSON.parse(storage.getItem(key) ?? "null"); } catch { return null; }
}

function readSession<Sort extends string>(key: string, config: JournalConfig<Sort>) {
  const saved = readJson(sessionStorage, key);
  if (!saved || typeof saved !== "object" || !("state" in saved) || !saved.state || typeof saved.state !== "object") return null;
  const scrollY = "scrollY" in saved && typeof saved.scrollY === "number" && Number.isFinite(saved.scrollY) ? Math.max(0, saved.scrollY) : 0;
  return { state: normalize(saved.state, config), scrollY };
}

export function journalViewMatches(left: JournalState, right: JournalState) {
  return left.search === right.search && left.dateFrom === right.dateFrom && left.typeFilter === right.typeFilter
    && left.statusFilter === right.statusFilter && left.sortBy === right.sortBy && left.sortOrder === right.sortOrder;
}

export function useJournalState<Sort extends string>(config: JournalConfig<Sort>) {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const sessionKey = `buy-modern-journal:${user?.id}:${config.id}`;
  const viewsKey = `${sessionKey}:views`;
  const initial = useMemo(() => readSession(sessionKey, config), [sessionKey, config]);
  const stateRef = useRef(initial?.state ?? defaults(config));
  const query = params.toString();
  const hasQuery = queryKeys.some((key) => params.has(key));
  const state = useMemo(() => hasQuery ? fromQuery(new URLSearchParams(query), config) : stateRef.current, [query, hasQuery, config]);
  const signature = JSON.stringify(state);
  useLayoutEffect(() => { stateRef.current = state; }, [signature]);
  const pendingScroll = useRef<{ signature: string; y: number } | null>({
    signature,
    y: initial && JSON.stringify(initial.state) === signature ? initial.scrollY : 0,
  });
  const scrollYRef = useRef(pendingScroll.current?.y ?? 0);
  const [loadedSignature, setLoadedSignature] = useState<string | null>(null);
  const [views, setViews] = useState<JournalView<Sort>[]>(() => {
    const stored = readJson(localStorage, viewsKey);
    if (!Array.isArray(stored)) return [];
    return stored.slice(0, 50).flatMap((item) => item && typeof item.id === "string" && typeof item.name === "string" && item.state && typeof item.state === "object"
      ? [{ id: item.id, name: item.name.slice(0, 80), state: { ...normalize(item.state, config), page: 0 } }] : []);
  });

  const persist = useCallback(() => {
    const pending = pendingScroll.current;
    try {
      sessionStorage.setItem(sessionKey, JSON.stringify({ state: stateRef.current, scrollY: pending?.signature === JSON.stringify(stateRef.current) ? pending.y : scrollYRef.current }));
    } catch { /* List navigation remains available when browser storage is disabled. */ }
  }, [sessionKey]);

  useEffect(() => {
    const canonical = toQuery(new URLSearchParams(query), state, config);
    if (canonical.toString() !== query) setParams(canonical, { replace: true, preventScrollReset: true });
    persist();
  }, [signature, hasQuery, query, config, setParams, persist]);

  useLayoutEffect(() => {
    let frame = 0;
    const onScroll = () => {
      scrollYRef.current = window.scrollY;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(persist);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("pagehide", persist);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pagehide", persist);
      persist();
    };
  }, [persist]);

  useLayoutEffect(() => {
    const pending = pendingScroll.current;
    if (!pending || pending.signature !== signature || loadedSignature !== signature) return;
    const frame = requestAnimationFrame(() => {
      window.scrollTo(0, pending.y);
      scrollYRef.current = window.scrollY;
      pendingScroll.current = null;
      persist();
    });
    return () => cancelAnimationFrame(frame);
  }, [loadedSignature, signature, persist]);

  function update(patch: Partial<JournalState<Sort>>) {
    pendingScroll.current = null;
    scrollYRef.current = window.scrollY;
    const next = normalize({ ...stateRef.current, ...patch }, config);
    stateRef.current = next;
    setParams(toQuery(params, next, config), { replace: true, preventScrollReset: true, flushSync: true });
  }

  function replaceViews(next: JournalView<Sort>[]) {
    try {
      localStorage.setItem(viewsKey, JSON.stringify(next));
      setViews(next);
      return true;
    } catch { return false; }
  }

  return {
    state,
    update,
    reset: () => update(defaults(config)),
    markLoaded: () => setLoadedSignature(signature),
    views,
    saveView: (name: string) => replaceViews([...views, { id: crypto.randomUUID(), name: name.trim(), state: { ...state, page: 0 } }]),
    deleteView: (id: string) => replaceViews(views.filter((view) => view.id !== id)),
    applyView: (view: JournalView<Sort>) => update({ ...view.state, page: 0 }),
  };
}
