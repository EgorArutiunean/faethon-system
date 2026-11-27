import { expect, Page, test } from "@playwright/test";

const permissions = ["documents.read", "documents.create", "documents.update", "documents.post", "documents.cancel", "documents.delete", "payments.read", "payments.create", "payments.update", "payments.post", "payments.cancel", "payments.delete", "payments.allocate", "partners.read", "warehouses.read", "products.read", "stock.read", "cash.read", "reports.read", "logistics.read", "logistics.review"];
const partner = { id: 2, name: "Клиент связанных операций", code: "REL-C", partner_type: "both", is_active: true };
const warehouse = { id: 1, name: "Склад связанных операций", code: "REL-W" };
const document = { id: 42, number: "OUT-REL-42", document_type: "outgoing", document_date: "2026-10-22", status: "posted", partner_id: 2, partner_name: partner.name, warehouse_id: 1, warehouse_name: warehouse.name, total_amount: "100.00", currency_code: "RUB_PMR", exchange_rate: "1", foreign_total_amount: "100.00", posting_version: 2, updated_at: "2026-10-22T08:00:00Z", lines: [] };
const originalPayment = { id: 7, updated_at: "2026-10-22T08:00:00Z", partner_id: 2, partner_name: partner.name, document_id: 42, document_number: document.number, payment_date: "2026-10-22", payment_type: "customer_payment", amount: "30.00", method: "cash", status: "draft", allocations: [{ id: 1, payment_id: 7, document_id: 42, document_number: document.number, document_date: document.document_date, amount: "30.00" }], allocated_amount: "30.00", unallocated_amount: "0.00" };

async function mockConnectedApi(page: Page, allowedPermissions = permissions) {
  const state = {
    summary: { document_id: 42, document_number: document.number, document_type: "outgoing", document_status: "posted", partner_id: 2, partner_name: partner.name, total_amount: "100.00", paid_amount: "30.00", outstanding_amount: "70.00", payment_type: "customer_payment", payments_count: 3, payments: [
      { id: 3, payment_date: "2026-10-20", payment_type: "customer_payment", status: "posted", amount: "90.00", allocated_amount_for_document: "30.00" },
      { id: 4, payment_date: "2026-10-21", payment_type: "customer_payment", status: "draft", amount: "20.00", allocated_amount_for_document: "20.00" },
      { id: 5, payment_date: "2026-10-21", payment_type: "customer_payment", status: "cancelled", amount: "10.00", allocated_amount_for_document: "10.00" },
    ] },
    payment: structuredClone(originalPayment),
    optionsOutstanding: "70.00",
    paymentRows: [structuredClone(originalPayment)],
    mutations: [] as Array<{ path: string; method: string; payload: Record<string, unknown> }>,
    documentQueries: [] as string[],
    summaryRequests: 0,
    paymentReads: 0,
    failCreate: false,
    saveDelay: null as Promise<void> | null,
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith("/auth/login")) { await route.fulfill({ json: { access_token: "connected-manager", token_type: "bearer" } }); return; }
    if (path.endsWith("/auth/me")) { await route.fulfill({ json: { id: 2, email: "manager@example.com", full_name: "Менеджер связанных операций", role_names: ["manager"], permissions: allowedPermissions, must_change_password: false } }); return; }
    if (path.endsWith("/auth/logout")) { await route.fulfill({ status: 204 }); return; }
    if (path.endsWith("/payments/document-summary/42")) { state.summaryRequests += 1; await route.fulfill({ json: state.summary }); return; }
    if (path.endsWith("/documents/42")) { await route.fulfill({ json: document }); return; }
    if (path.endsWith("/documents/42/revisions")) { await route.fulfill({ json: [] }); return; }
    if (path.endsWith("/payments/page")) {
      state.documentQueries.push(url.searchParams.get("document_id") ?? "");
      await route.fulfill({ json: { items: state.paymentRows, total: state.paymentRows.length, offset: 0, limit: 25 } }); return;
    }
    if (path.endsWith("/payments/7") && request.method() === "GET") { state.paymentReads += 1; await route.fulfill({ json: state.payment }); return; }
    if (path.endsWith("/payments/allocation-options")) { await route.fulfill({ json: [{ document_id: 42, document_number: document.number, document_date: document.document_date, total_amount: "100.00", allocated_amount: "30.00", outstanding_amount: state.optionsOutstanding }] }); return; }
    if (path.endsWith("/payments") && request.method() === "POST") {
      const payload = request.postDataJSON() as Record<string, unknown>;
      state.mutations.push({ path, method: "POST", payload });
      if (state.saveDelay) await state.saveDelay;
      if (state.failCreate) { await route.fulfill({ status: 409, json: { detail: "Связь прервана. Повторите сохранение." } }); return; }
      const created = { ...structuredClone(originalPayment), ...payload, id: 9 };
      state.paymentRows.push(created as typeof originalPayment);
      await route.fulfill({ status: 201, json: created }); return;
    }
    if (path.endsWith("/payments/7") && request.method() === "PATCH") {
      state.mutations.push({ path, method: "PATCH", payload: request.postDataJSON() as Record<string, unknown> });
      if (state.saveDelay) await state.saveDelay;
      await route.fulfill({ json: { ...state.payment, ...request.postDataJSON(), updated_at: "2026-10-22T10:00:00Z" } }); return;
    }
    if (path.endsWith("/payments/7/allocations") && request.method() === "PUT") {
      state.mutations.push({ path, method: "PUT", payload: request.postDataJSON() as Record<string, unknown> });
      if (state.saveDelay) await state.saveDelay;
      await route.fulfill({ json: state.payment }); return;
    }
    if (path.endsWith("/logistics/tasks")) { await route.fulfill({ json: [
      { id: 8, document_id: 42, document_number: document.number, posting_version: 2, document_date: document.document_date, document_type: "outgoing", warehouse_id: 1, warehouse_name: warehouse.name, task_type: "outgoing_dispatch", status: "pending", created_at: "2026-10-22T08:00:00Z", lines: [], events: [] },
      { id: 6, document_id: 42, document_number: document.number, posting_version: 1, document_date: document.document_date, document_type: "outgoing", warehouse_id: 1, warehouse_name: warehouse.name, task_type: "outgoing_dispatch", status: "cancelled", created_at: "2026-10-20T08:00:00Z", lines: [], events: [] },
    ] }); return; }
    if (path.endsWith("/partners/2/balance")) { await route.fulfill({ json: { partner_id: 2, partner_name: partner.name, partner_type: "both", balance: "70.00" } }); return; }
    if (path.endsWith("/partners/2")) { await route.fulfill({ json: partner }); return; }
    if (path.endsWith("/partners/options")) { await route.fulfill({ json: [partner] }); return; }
    if (path.endsWith("/warehouses")) { await route.fulfill({ json: [warehouse] }); return; }
    if (path.endsWith("/currencies")) { await route.fulfill({ json: [{ id: 1, code: "RUB_PMR", name: "Рубль ПМР", symbol: "руб.", is_base: true, is_active: true }] }); return; }
    if (path.endsWith("/dashboard/summary")) { await route.fulfill({ json: { products_count: 0, partners_count: 1, documents_count: 1, outgoing_total: "100.00", incoming_total: "0.00", document_statuses: { posted: 1 }, document_types: { outgoing: 1 }, payment_statuses: {}, stock_positions_count: 0, stock_total_quantity: "0.000", top_warehouses: [], cash_balance: "0.00", recent_documents: [] } }); return; }
    await route.fulfill({ json: [] });
  });
  return state;
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("manager@example.com");
  await page.getByLabel("Пароль").fill("manager123");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByTestId("header-user")).toBeVisible();
}

test("CONNECTED-01: документ показывает оплату и склад, готовит связанную частичную оплату без автоматической записи", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/documents/42");
  await expect(page.getByTestId("document-paid")).toHaveText(/30[,.]00/);
  await expect(page.getByTestId("document-outstanding")).toHaveText(/70[,.]00/);
  await expect(page.getByRole("link", { name: "Открыть задание #8", exact: true })).toHaveAttribute("href", "/logistics?task=8");
  await expect(page.getByRole("link", { name: "Открыть задание #6", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Принять оплату", exact: true }).click();
  await expect(page.getByTestId("payment-partner")).toHaveValue("2");
  await expect(page.getByTestId("payment-type")).toHaveValue("customer_payment");
  await expect(page.getByTestId("payment-amount")).toHaveValue("70.00");
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("70.00");
  expect(state.mutations).toHaveLength(0);
  await page.getByTestId("payment-amount").fill("25");
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("25.00");
  await page.getByTestId("payment-save").click();
  await expect.poll(() => state.mutations.length).toBe(1);
  expect(state.mutations[0].payload).toMatchObject({ partner_id: 2, payment_type: "customer_payment", status: "draft", amount: "25", allocations: [{ document_id: 42, amount: "25.00" }] });
  await expect(page.getByTestId("payment-amount")).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("payment-amount")).toHaveCount(0);
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toHaveCount(0);
  expect(state.mutations.every((mutation) => !mutation.path.endsWith("/post"))).toBe(true);
});

test("CONNECTED-02: переход к оплатам документа использует точный серверный фильтр", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/documents/42");
  await page.getByRole("link", { name: "Открыть оплаты документа (3)", exact: true }).click();
  await expect.poll(() => state.documentQueries.at(-1)).toBe("42");
  await expect(page.getByTestId("payment-amount")).toHaveCount(0);
  await page.getByRole("link", { name: "Все оплаты", exact: true }).click();
  await expect.poll(() => state.documentQueries.at(-1)).toBe("");
  expect(state.mutations).toHaveLength(0);
});

test("CONNECTED-03: недоступная или подменённая ссылка не создаёт форму связанной оплаты", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  for (const scenario of [
    { document_status: "draft", outstanding_amount: "70.00", create: "customer_payment" },
    { document_status: "posted", outstanding_amount: "0.00", create: "customer_payment" },
    { document_status: "posted", outstanding_amount: "70.00", create: "supplier_payment" },
  ]) {
    Object.assign(state.summary, scenario);
    await page.goto(`/payments?document_id=42&create=${scenario.create}&page=1`);
    await expect(page.getByText("Не удалось подготовить оплату: документ или остаток изменился. Откройте его карточку и повторите действие.", { exact: true })).toBeVisible();
    await expect(page.getByTestId("payment-amount")).toHaveCount(0);
  }
  expect(state.mutations).toHaveLength(0);
});

test("CONNECTED-04: роль без финансового чтения не запрашивает и не показывает сводку оплат", async ({ page }) => {
  const state = await mockConnectedApi(page, permissions.filter((permission) => !permission.startsWith("payments.")));
  await login(page);
  await page.goto("/documents/42");
  await expect(page.getByRole("region", { name: "Складские задания документа", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Оплаты документа", exact: true })).toHaveCount(0);
  expect(state.summaryRequests).toBe(0);
});

test("RECOVERY-PAYMENT-01: новый ввод и неудачное сохранение восстанавливаются, явная отмена очищает их", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/payments?page=1");
  await page.getByRole("button", { name: "Создать оплату", exact: true }).click();
  await page.getByTestId("payment-partner").selectOption("2");
  await page.getByTestId("payment-amount").fill("12.34");
  await page.getByTestId("payment-allocation-42").fill("10");
  await page.reload();
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toBeVisible();
  await expect(page.getByTestId("payment-amount")).toHaveValue("12.34");
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("10");
  expect(state.mutations).toHaveLength(0);
  state.failCreate = true;
  await page.getByTestId("payment-save").click();
  await expect(page.getByText(/Связь прервана\. Повторите сохранение\./)).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("payment-amount")).toHaveValue("12.34");
  await page.locator(".payment-editor").getByRole("button", { name: "Отменить", exact: true }).click();
  await page.reload();
  await expect(page.getByTestId("payment-amount")).toHaveCount(0);
  await page.getByRole("button", { name: "Создать оплату", exact: true }).click();
  await expect(page.getByTestId("payment-amount")).toHaveValue("");
  expect(state.mutations).toHaveLength(1);
});

test("RECOVERY-PAYMENT-02: ввод редактируемой оплаты восстанавливается только для той же серверной версии", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/payments?edit_payment=7&page=1");
  await expect(page.getByTestId("payment-amount")).toHaveValue("30.00");
  await page.getByTestId("payment-amount").fill("45");
  await page.reload();
  await expect(page.getByTestId("payment-amount")).toHaveValue("45");
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toBeVisible();
  state.payment.updated_at = "2026-10-22T09:00:00Z";
  state.payment.amount = "35.00";
  await page.reload();
  await expect(page.getByText("Сохранённый ввод относится к прежней версии записи. Проверьте актуальные данные.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("payment-amount")).toHaveValue("35.00");
  await page.getByRole("button", { name: "Удалить сохранённый ввод", exact: true }).click();
  await expect(page.getByText("Сохранённый ввод относится к прежней версии записи. Проверьте актуальные данные.", { exact: true })).toHaveCount(0);
  expect(state.mutations).toHaveLength(0);
});

test("RECOVERY-PAYMENT-03: распределение проведённой оплаты восстанавливается и проверяет текущие остатки", async ({ page }) => {
  const state = await mockConnectedApi(page);
  state.payment.status = "posted";
  await login(page);
  await page.goto("/payments?allocate_payment=7&page=1");
  await page.getByTestId("payment-allocation-42").fill("20");
  await page.reload();
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("20");
  state.optionsOutstanding = "60.00";
  await page.reload();
  await expect(page.getByText("Сохранённый ввод относится к прежней версии записи. Проверьте актуальные данные.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("30.00");
  expect(state.mutations).toHaveLength(0);
});

test("RECOVERY-PAYMENT-04: связанная оплата сохраняет частичный ввод и не восстанавливает его при изменившемся остатке", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/payments?document_id=42&create=customer_payment&page=1");
  await expect(page.getByTestId("payment-amount")).toHaveValue("70.00");
  await page.getByTestId("payment-amount").fill("25");
  await page.reload();
  await expect(page.getByTestId("payment-amount")).toHaveValue("25");
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("25.00");
  state.summary.outstanding_amount = "15.00";
  state.summary.paid_amount = "85.00";
  state.optionsOutstanding = "15.00";
  await page.reload();
  await expect(page.getByText("Сохранённый ввод относится к прежней версии записи. Проверьте актуальные данные.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("payment-amount")).toHaveValue("15.00");
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("15.00");
  expect(state.mutations).toHaveLength(0);
});

test("RECOVERY-PAYMENT-05: быстрые приход и выплата восстанавливают разные формы", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/payments?create=customer_payment&page=1");
  await page.getByTestId("payment-partner").selectOption("2");
  await page.getByTestId("payment-amount").fill("18.50");
  await page.goto("/payments?create=supplier_payment&page=1");
  await expect(page.getByTestId("payment-type")).toHaveValue("supplier_payment");
  await expect(page.getByTestId("payment-partner")).toHaveValue("");
  await expect(page.getByTestId("payment-amount")).toHaveValue("");
  await page.getByTestId("payment-partner").selectOption("2");
  await page.getByTestId("payment-amount").fill("26.75");
  await page.goto("/payments?create=customer_payment&page=1");
  await expect(page.getByTestId("payment-type")).toHaveValue("customer_payment");
  await expect(page.getByTestId("payment-amount")).toHaveValue("18.50");
  await page.goto("/payments?create=supplier_payment&page=1");
  await expect(page.getByTestId("payment-amount")).toHaveValue("26.75");
  expect(state.mutations).toHaveLength(0);
});

test("RECOVERY-PAYMENT-06: намеренная смена направления восстанавливается в том же черновике", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/payments?create=customer_payment&page=1");
  await page.getByTestId("payment-partner").selectOption("2");
  await page.getByTestId("payment-type").selectOption("supplier_payment");
  await page.getByTestId("payment-amount").fill("23.50");
  await page.reload();
  await expect(page.getByTestId("payment-type")).toHaveValue("supplier_payment");
  await expect(page.getByTestId("payment-partner")).toHaveValue("2");
  await expect(page.getByTestId("payment-amount")).toHaveValue("23.50");
  expect(state.mutations).toHaveLength(0);
});

test("RECOVERY-PAYMENT-07: открытие строки журнала проверяет свежую серверную версию перед восстановлением", async ({ page }) => {
  const state = await mockConnectedApi(page);
  await login(page);
  await page.goto("/payments?edit_payment=7&page=1");
  await page.getByTestId("payment-amount").fill("45");
  await page.goto("/payments?page=1");
  state.payment.amount = "55.00";
  state.payment.updated_at = "2026-10-22T11:00:00Z";
  const readsBeforeOpen = state.paymentReads;
  await page.getByRole("button", { name: "Изменить", exact: true }).click();
  await expect(page.getByTestId("payment-amount")).toHaveValue("55.00");
  await expect(page.getByText("Сохранённый ввод относится к прежней версии записи. Проверьте актуальные данные.", { exact: true })).toBeVisible();
  expect(state.paymentReads).toBeGreaterThan(readsBeforeOpen);
  expect(state.mutations).toHaveLength(0);
});

test("RECOVERY-PAYMENT-08: изменение распределения проверяется даже без изменения даты самой оплаты", async ({ page }) => {
  const state = await mockConnectedApi(page);
  state.payment.status = "posted";
  await login(page);
  await page.goto("/payments?allocate_payment=7&page=1");
  await page.getByTestId("payment-allocation-42").fill("20");
  state.payment.allocations[0].amount = "25.00";
  state.payment.allocated_amount = "25.00";
  state.payment.unallocated_amount = "5.00";
  await page.reload();
  await expect(page.getByText("Сохранённый ввод относится к прежней версии записи. Проверьте актуальные данные.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("payment-allocation-42")).toHaveValue("25.00");
  expect(state.mutations).toHaveLength(0);
});

test("PAYMENT-SAVE-01: во время сохранения строки заблокированы, поздний ответ сохраняет новый контекст журнала", async ({ page }) => {
  const state = await mockConnectedApi(page);
  let releaseSave!: () => void;
  state.saveDelay = new Promise<void>((resolve) => { releaseSave = resolve; });
  await login(page);
  await page.goto("/payments?document_id=42&create=customer_payment&page=1");
  await page.getByTestId("payment-amount").fill("25");
  await page.getByTestId("payment-save").click();
  await expect.poll(() => state.mutations.length).toBe(1);
  await expect(page.getByRole("button", { name: "Изменить", exact: true })).toBeDisabled();
  await expect(page.getByTestId("payment-post-7")).toBeDisabled();
  await page.getByRole("link", { name: "Все оплаты", exact: true }).click();
  await expect.poll(() => state.documentQueries.at(-1)).toBe("");
  await page.getByRole("textbox", { name: "Поиск", exact: true }).fill("Новый поиск");
  const completed = page.waitForResponse((response) => response.url().endsWith("/api/v1/payments") && response.request().method() === "POST");
  releaseSave();
  await completed;
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page).not.toHaveURL(/document_id=42/);
  await expect(page.getByRole("textbox", { name: "Поиск", exact: true })).toHaveValue("Новый поиск");
  await expect(page.getByTestId("payment-amount")).toHaveCount(0);
  expect(state.mutations).toHaveLength(1);
});

test("PAYMENT-SAVE-02: завершение оплаты после ухода со страницы не возвращает пользователя в журнал", async ({ page }) => {
  const state = await mockConnectedApi(page);
  let releaseSave!: () => void;
  state.saveDelay = new Promise<void>((resolve) => { releaseSave = resolve; });
  await login(page);
  await page.goto("/payments?document_id=42&create=customer_payment&page=1");
  await page.getByTestId("payment-save").click();
  await expect.poll(() => state.mutations.length).toBe(1);
  await page.locator(".payment-document-context").getByRole("link", { name: /Документ/ }).click();
  await expect(page.getByRole("heading", { name: /OUT-REL-42/ })).toBeVisible();
  const completed = page.waitForResponse((response) => response.url().endsWith("/api/v1/payments") && response.request().method() === "POST");
  releaseSave();
  await completed;
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page).toHaveURL(/\/documents\/42$/);
  await expect(page.getByRole("heading", { name: /OUT-REL-42/ })).toBeVisible();
  expect(state.mutations).toHaveLength(1);
});
