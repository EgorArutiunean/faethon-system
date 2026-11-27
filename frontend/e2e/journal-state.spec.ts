import { expect, Page, test } from "@playwright/test";

type JournalState = {
  q: string;
  date_from: string;
  type: string;
  status: string;
  sort: string;
  order: "asc" | "desc";
  page: number;
};

const warehouse = { id: 1, code: "MAIN", name: "Основной склад", address: null };
const partner = { id: 2, code: "WHOLESALE", name: "Оптовый клиент", partner_type: "both", is_active: true };
const permissions = [
  "documents.read", "documents.create", "documents.update", "documents.post", "documents.cancel", "documents.delete",
  "payments.read", "payments.create", "payments.update", "payments.post", "payments.cancel", "payments.delete", "payments.allocate",
  "partners.read", "warehouses.read", "products.read", "stock.read", "cash.read", "reports.read",
];

const documents = Array.from({ length: 80 }, (_, index) => ({
  id: index + 1,
  number: `DOC-${String(index + 1).padStart(3, "0")}`,
  document_date: "2026-10-20",
  document_type: index < 70 ? "outgoing" : "incoming",
  status: index < 70 ? "draft" : "posted",
  partner_id: partner.id,
  partner_name: partner.name,
  warehouse_id: warehouse.id,
  warehouse_name: warehouse.name,
  total_amount: String((index + 1) * 100),
  currency_code: "RUB_PMR",
  exchange_rate: "1.000000",
  foreign_total_amount: String((index + 1) * 100),
  posting_version: index < 70 ? 0 : 1,
  lines: [],
}));

const payments = Array.from({ length: 80 }, (_, index) => ({
  id: index + 1,
  payment_date: "2026-10-20",
  payment_type: index < 70 ? "customer_payment" : "supplier_payment",
  status: index < 70 ? "draft" : "posted",
  partner_id: partner.id,
  partner_name: partner.name,
  amount: String((index + 1) * 100),
  allocated_amount: "0.00",
  unallocated_amount: String((index + 1) * 100),
  allocations: [],
  method: "cash",
}));

async function mockJournalApi(page: Page) {
  let currentEmail = "manager@example.com";
  const queries = { documents: [] as URLSearchParams[], payments: [] as URLSearchParams[] };

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith("/auth/login")) {
      currentEmail = (request.postDataJSON() as { email: string }).email;
      await route.fulfill({ json: { access_token: `token-${currentEmail}`, token_type: "bearer" } });
      return;
    }
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: {
        id: currentEmail === "manager@example.com" ? 2 : 3,
        email: currentEmail,
        full_name: currentEmail === "manager@example.com" ? "Первый менеджер" : "Второй менеджер",
        role_names: ["manager"], permissions, must_change_password: false,
      } });
      return;
    }
    if (path.endsWith("/auth/logout")) {
      await route.fulfill({ status: 204 });
      return;
    }
    if (path.endsWith("/documents/page") || path.endsWith("/payments/page")) {
      const isDocument = path.endsWith("/documents/page");
      queries[isDocument ? "documents" : "payments"].push(new URLSearchParams(url.searchParams));
      const params = url.searchParams;
      const search = params.get("search")?.toLowerCase() ?? "";
      const type = params.get(isDocument ? "document_type" : "payment_type") ?? "";
      const status = params.get("status") ?? "";
      const dateFrom = params.get("date_from") ?? "";
      const sort = params.get("sort_by") ?? (isDocument ? "document_date" : "payment_date");
      const order = params.get("sort_order") === "asc" ? 1 : -1;
      const filtered = (isDocument ? documents : payments).filter((row) => {
        const record = row as unknown as Record<string, unknown>;
        return (!search || `${record.number ?? ""} ${record.partner_name}`.toLowerCase().includes(search))
          && (!type || record[isDocument ? "document_type" : "payment_type"] === type)
          && (!status || record.status === status)
          && (!dateFrom || String(record[isDocument ? "document_date" : "payment_date"]) >= dateFrom);
      });
      filtered.sort((a, b) => {
        const left = String((a as unknown as Record<string, unknown>)[sort] ?? "");
        const right = String((b as unknown as Record<string, unknown>)[sort] ?? "");
        return order * (left.localeCompare(right, undefined, { numeric: true }) || a.id - b.id);
      });
      const offset = Number(params.get("offset") ?? 0);
      const limit = Number(params.get("limit") ?? 25);
      await route.fulfill({ json: { items: filtered.slice(offset, offset + limit), total: filtered.length, offset, limit } });
      return;
    }
    const documentId = path.match(/\/documents\/(\d+)$/)?.[1];
    if (documentId) {
      await route.fulfill({ json: documents.find((row) => row.id === Number(documentId)) });
      return;
    }
    const summaryId = path.match(/\/payments\/document-summary\/(\d+)$/)?.[1];
    if (summaryId) {
      const doc = documents.find((row) => row.id === Number(summaryId))!;
      await route.fulfill({ json: {
        document_id: doc.id, document_number: doc.number, document_type: doc.document_type, document_status: doc.status,
        partner_id: doc.partner_id, partner_name: doc.partner_name, total_amount: doc.total_amount, paid_amount: "0.00", outstanding_amount: doc.status === "posted" ? doc.total_amount : "0.00",
        payment_type: doc.document_type === "incoming" ? "supplier_payment" : "customer_payment", payments_count: 0, payments: [],
      } });
      return;
    }
    if (path.endsWith("/dashboard/summary")) {
      await route.fulfill({ json: {
        products_count: 0, partners_count: 1, documents_count: documents.length,
        outgoing_total: "0.00", incoming_total: "0.00", document_statuses: { draft: 70, posted: 10 },
        document_types: { outgoing: 70, incoming: 10 }, payment_statuses: { draft: 70, posted: 10 },
        stock_positions_count: 0, stock_total_quantity: "0.000", top_warehouses: [],
        cash_balance: "0.00", recent_documents: [],
      } });
      return;
    }
    if (path.endsWith("/warehouses")) {
      await route.fulfill({ json: [warehouse] });
      return;
    }
    if (path.endsWith("/partners/options")) {
      await route.fulfill({ json: [partner] });
      return;
    }
    if (path.endsWith("/partners/2")) {
      await route.fulfill({ json: partner });
      return;
    }
    if (path.endsWith("/currencies")) {
      await route.fulfill({ json: [{ id: 1, code: "RUB_PMR", name: "Рубль ПМР", symbol: "руб.", is_base: true, is_active: true }] });
      return;
    }
    await route.fulfill({ json: [] });
  });
  return queries;
}

async function login(page: Page, email = "manager@example.com") {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("manager123");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByTestId("header-user")).toBeVisible();
}

async function openJournal(page: Page, name: "Документы" | "Оплаты") {
  await page.locator(".sidebar-nav").getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

async function expectJournalState(page: Page, state: JournalState) {
  for (const [key, value] of Object.entries(state)) {
    await expect.poll(() => {
      const url = new URL(page.url());
      const defaultValue = key === "sort" ? (url.pathname === "/payments" ? "payment_date" : "document_date") : key === "order" ? "desc" : "";
      return url.searchParams.get(key) ?? defaultValue;
    }).toBe(String(value));
  }
  await expect(page.getByRole("textbox", { name: "Поиск", exact: true })).toHaveValue(state.q);
  await expect(page.getByLabel("С даты")).toHaveValue(state.date_from);
  await expect(page.getByRole("combobox", { name: "Фильтр: Тип", exact: true })).toHaveValue(state.type);
  await expect(page.getByRole("combobox", { name: "Фильтр: Статус", exact: true })).toHaveValue(state.status);
  await expect(page.getByRole("combobox", { name: "Сортировать по", exact: true })).toHaveValue(state.sort);
  await expect(page.getByRole("button", { name: "Направление сортировки", exact: true })).toHaveText(state.order === "asc" ? "↑" : "↓");
}

async function setWholesaleFilters(page: Page, kind: "documents" | "payments") {
  await page.getByRole("textbox", { name: "Поиск", exact: true }).fill("Оптовый");
  await page.getByLabel("С даты").fill("2026-10-01");
  await page.getByRole("combobox", { name: "Фильтр: Тип", exact: true }).selectOption(kind === "documents" ? "outgoing" : "customer_payment");
  await page.getByRole("combobox", { name: "Фильтр: Статус", exact: true }).selectOption("draft");
  await page.getByRole("combobox", { name: "Сортировать по", exact: true }).selectOption(kind === "documents" ? "number" : "amount");
  await page.getByRole("button", { name: "Направление сортировки", exact: true }).click();
}

const documentView: JournalState = { q: "Оптовый", date_from: "2026-10-01", type: "outgoing", status: "draft", sort: "number", order: "asc", page: 1 };
const paymentView: JournalState = { ...documentView, type: "customer_payment", sort: "amount" };

async function saveView(page: Page, name: string) {
  await page.getByRole("button", { name: "Сохранить представление", exact: true }).click();
  await page.getByRole("textbox", { name: "Название представления", exact: true }).fill(name);
  await page.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Сохранённое представление", exact: true }).locator("option:checked")).toHaveText(name);
}

test("JOURNAL-01: карточка документа возвращает фильтры, страницу и позицию журнала", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const queries = await mockJournalApi(page);
  await login(page);
  await openJournal(page, "Документы");
  await setWholesaleFilters(page, "documents");
  await expectJournalState(page, documentView);
  await expect.poll(() => queries.documents.at(-1)?.get("sort_order")).toBe("asc");
  await page.getByRole("button", { name: "›", exact: true }).click();
  await expectJournalState(page, { ...documentView, page: 2 });
  await expect.poll(() => queries.documents.at(-1)?.get("offset")).toBe("25");
  await openJournal(page, "Документы");
  await expectJournalState(page, { ...documentView, page: 2 });
  const documentLink = page.getByRole("link", { name: "DOC-038", exact: true });
  await documentLink.scrollIntoViewIfNeeded();
  const scrollBeforeOpening = await page.evaluate(() => window.scrollY);
  expect(scrollBeforeOpening).toBeGreaterThan(300);
  await documentLink.click();
  await expect(page).toHaveURL(/\/documents\/38$/);
  await page.locator(".document-back").click();
  await expectJournalState(page, { ...documentView, page: 2 });
  await expect(page.getByRole("link", { name: "DOC-038", exact: true })).toBeVisible();
  await expect.poll(async () => Math.abs((await page.evaluate(() => window.scrollY)) - scrollBeforeOpening)).toBeLessThan(6);
  await page.reload();
  await expectJournalState(page, { ...documentView, page: 2 });
  await expect.poll(() => queries.documents.at(-1)?.get("offset")).toBe("25");
  await expect.poll(async () => Math.abs((await page.evaluate(() => window.scrollY)) - scrollBeforeOpening)).toBeLessThan(6);
  await page.getByRole("link", { name: "DOC-038", exact: true }).click();
  await expect(page).toHaveURL(/\/documents\/38$/);
  await page.goBack();
  await expectJournalState(page, { ...documentView, page: 2 });
  await expect.poll(async () => Math.abs((await page.evaluate(() => window.scrollY)) - scrollBeforeOpening)).toBeLessThan(6);
});

test("JOURNAL-02: оплаты сохраняют настройки и страницу после перехода и обновления", async ({ page }) => {
  const queries = await mockJournalApi(page);
  await login(page);
  await openJournal(page, "Оплаты");
  await setWholesaleFilters(page, "payments");
  await expectJournalState(page, paymentView);
  await expect.poll(() => queries.payments.at(-1)?.get("sort_by")).toBe("amount");
  await page.getByRole("button", { name: "›", exact: true }).click();
  await expectJournalState(page, { ...paymentView, page: 2 });
  await expect.poll(() => queries.payments.at(-1)?.get("offset")).toBe("25");
  await openJournal(page, "Оплаты");
  await expectJournalState(page, { ...paymentView, page: 2 });
  await openJournal(page, "Документы");
  await openJournal(page, "Оплаты");
  await expectJournalState(page, { ...paymentView, page: 2 });
  await page.reload();
  await expectJournalState(page, { ...paymentView, page: 2 });
  await expect.poll(() => queries.payments.at(-1)?.get("offset")).toBe("25");
});

for (const journal of [
  { route: "documents", title: "Документы", view: documentView, name: "Оптовые расходы" },
  { route: "payments", title: "Оплаты", view: paymentView, name: "Оплаты оптовиков" },
] as const) {
  test(`JOURNAL-03-${journal.route}: именованное представление сохраняется, применяется с первой страницы и удаляется`, async ({ page }) => {
    await mockJournalApi(page);
    await login(page);
    await openJournal(page, journal.title);
    await setWholesaleFilters(page, journal.route);
    await expectJournalState(page, journal.view);
    await expect(page.getByRole("button", { name: "›", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "›", exact: true }).click();
    await expectJournalState(page, { ...journal.view, page: 2 });
    await saveView(page, journal.name);
    await page.reload();
    const views = page.getByRole("combobox", { name: "Сохранённое представление", exact: true });
    await expect(views.locator("option:checked")).toHaveText(journal.name);
    await page.getByRole("button", { name: "Сбросить фильтры", exact: true }).click();
    await expect(views.locator("option:checked")).toHaveText("Текущие настройки");
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await expect(page.getByRole("button", { name: "›", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "›", exact: true }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get("page")).toBe("2");
    await views.selectOption({ label: journal.name });
    await expectJournalState(page, journal.view);
    await page.getByRole("button", { name: "Удалить представление", exact: true }).click();
    await expect(views.locator("option")).toHaveCount(1);
    await expectJournalState(page, journal.view);
    await page.reload();
    await expect(views.locator("option")).toHaveCount(1);
    await expect(views.locator("option:checked")).toHaveText("Текущие настройки");
  });
}

test("JOURNAL-04: явные параметры ссылки заменяют сохранённые настройки журналов", async ({ page }) => {
  const queries = await mockJournalApi(page);
  await login(page);
  for (const journal of [
    { route: "documents", title: "Документы", type: "incoming", sort: "document_date" },
    { route: "payments", title: "Оплаты", type: "supplier_payment", sort: "payment_date" },
  ] as const) {
    await openJournal(page, journal.title);
    await setWholesaleFilters(page, journal.route);
    await expect(page.getByRole("button", { name: "›", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "›", exact: true }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get("page")).toBe("2");
    await page.goto(`/${journal.route}?status=posted&type=${journal.type}&date_from=2026-10-01`);
    await expectJournalState(page, {
      q: "", date_from: "2026-10-01", status: "posted", type: journal.type,
      sort: journal.sort, order: "desc", page: 1,
    });
    await expect.poll(() => queries[journal.route].at(-1)?.get("status")).toBe("posted");
    await expect.poll(() => queries[journal.route].at(-1)?.get("offset")).toBe("0");
    await expect(page.getByRole("button", { name: "›", exact: true })).toHaveCount(0);
  }
});

test("JOURNAL-05: настройки и представления принадлежат пользователю", async ({ page }) => {
  await mockJournalApi(page);
  await login(page);
  await openJournal(page, "Документы");
  await setWholesaleFilters(page, "documents");
  await expectJournalState(page, documentView);
  await saveView(page, "Расходы первого менеджера");
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await login(page, "second@example.com");
  await openJournal(page, "Документы");
  await expectJournalState(page, { q: "", date_from: "", type: "", status: "", sort: "document_date", order: "desc", page: 1 });
  await expect(page.getByRole("combobox", { name: "Сохранённое представление", exact: true }).locator("option")).toHaveCount(1);
  await page.getByRole("textbox", { name: "Поиск", exact: true }).fill("DOC-080");
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await login(page);
  await openJournal(page, "Документы");
  await expectJournalState(page, documentView);
  await expect(page.getByRole("combobox", { name: "Сохранённое представление", exact: true }).locator("option:checked")).toHaveText("Расходы первого менеджера");
});

test("JOURNAL-06: завершение оплаты обновляет журнал с текущими фильтрами", async ({ page }) => {
  const queries = await mockJournalApi(page);
  let releasePost!: () => void;
  const posting = new Promise<void>((resolve) => { releasePost = resolve; });
  let postStarted = false;
  await page.route("**/api/v1/payments/1/post", async (route) => {
    postStarted = true;
    await posting;
    await route.fulfill({ json: { ...payments[0], status: "posted" } });
  });
  await login(page);
  await page.goto("/payments?status=draft&sort=id&order=asc");
  await page.getByTestId("payment-post-1").click();
  await page.getByRole("dialog", { name: "Подтверждение действия" }).getByRole("button", { name: "Провести", exact: true }).click();
  await expect.poll(() => postStarted).toBe(true);
  await page.getByRole("combobox", { name: "Фильтр: Статус", exact: true }).selectOption("posted");
  await expect.poll(() => queries.payments.at(-1)?.get("status")).toBe("posted");
  await expect(page.getByTestId("payment-post-1")).toHaveCount(0);
  const refreshed = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/v1/payments/page");
  releasePost();
  await refreshed;
  expect(queries.payments.at(-1)?.get("status")).toBe("posted");
  await expect(page.getByRole("combobox", { name: "Фильтр: Статус", exact: true })).toHaveValue("posted");
  await expect(page.getByTestId("payment-post-1")).toHaveCount(0);
});
