import { expect, Page, test } from "@playwright/test";

const manager = {
  id: 2,
  email: "manager@example.com",
  full_name: "Тестовый менеджер",
  role_names: ["manager"],
  permissions: [
    "products.read",
    "products.create",
    "products.update",
    "warehouses.read",
    "warehouses.create",
    "warehouses.update",
    "partners.read",
    "partners.create",
    "partners.update",
    "documents.read",
    "documents.create",
    "documents.update",
    "documents.post",
    "documents.cancel",
    "documents.delete",
    "stock.read",
    "payments.read",
    "payments.create",
    "payments.update",
    "payments.delete",
    "payments.post",
    "payments.cancel",
    "payments.allocate",
    "cash.read",
    "cash.create",
    "cash.cancel",
    "reports.read",
  ],
  must_change_password: false,
};

const warehouse = { id: 1, code: "MAIN", name: "Основной склад", address: null };
const supplier = { id: 1, code: "SUP", name: "Тестовый поставщик", partner_type: "supplier", is_active: true };
const customer = { id: 2, code: "CUS", name: "Тестовый клиент", partner_type: "customer", is_active: true };
const product = { id: 1, sku: "TEST-1", name: "Тестовый товар", base_price: "100.00", is_active: true };

type ApiOverrides = {
  document?: Record<string, unknown>;
  onPostDocument?: () => void;
  products?: Array<Record<string, unknown>>;
  productGroups?: Array<Record<string, unknown>>;
  currentUser?: Record<string, unknown>;
  onChangePassword?: () => void;
  warehouseTasks?: Array<Record<string, unknown>>;
  onCreatePartner?: (payload: Record<string, unknown>) => void;
  paymentRows?: Array<Record<string, unknown>>;
};

async function mockManagerApi(page: Page, overrides: ApiOverrides = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path.endsWith("/auth/login") && request.method() === "POST") {
      await route.fulfill({ json: { access_token: "manager-token", token_type: "bearer" } });
      return;
    }
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: overrides.currentUser ?? manager });
      return;
    }
    if (path.endsWith("/auth/change-password") && request.method() === "POST") {
      overrides.onChangePassword?.();
      await route.fulfill({ json: manager });
      return;
    }
    if (path.endsWith("/dashboard/summary")) {
      await route.fulfill({
        json: {
          products_count: 1,
          partners_count: 2,
          documents_count: 0,
          outgoing_total: "0.00",
          incoming_total: "0.00",
          document_statuses: {},
          document_types: {},
          payment_statuses: {},
          stock_positions_count: 0,
          stock_total_quantity: "0.000",
          top_warehouses: [],
          cash_balance: "0.00",
          recent_documents: [],
        },
      });
      return;
    }
    if (/\/payments\/document-summary\/\d+$/.test(path)) {
      const doc = overrides.document ?? {};
      await route.fulfill({ json: {
        document_id: Number(path.split("/").at(-1)), document_number: doc.number ?? null, document_type: doc.document_type ?? "outgoing", document_status: doc.status ?? "draft",
        partner_id: doc.partner_id ?? null, partner_name: doc.partner_name ?? null, total_amount: doc.total_amount ?? "0.00", paid_amount: "0.00",
        outstanding_amount: doc.status === "posted" ? doc.total_amount ?? "0.00" : "0.00", payment_type: doc.document_type === "incoming" ? "supplier_payment" : "customer_payment", payments_count: 0, payments: [],
      } });
      return;
    }
    if (path === "/api/v1/documents/42/post" && request.method() === "POST") {
      overrides.onPostDocument?.();
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not enough stock for outgoing document" }),
      });
      return;
    }
    if (path === "/api/v1/documents/42") {
      await route.fulfill({ json: overrides.document });
      return;
    }
    if (path === "/api/v1/documents/page") {
      await route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 25 } });
      return;
    }
    if (path.endsWith("/currencies")) {
      await route.fulfill({
        json: [
          { id: 1, code: "RUB_PMR", name: "Рубль ПМР", symbol: "руб.", is_base: true, is_active: true },
          { id: 2, code: "USD", name: "Доллар США", symbol: "$", is_base: false, is_active: true },
        ],
      });
      return;
    }
    if (path.endsWith("/currencies/rates/latest")) {
      await route.fulfill({ json: { id: 1, currency_id: 2, currency_code: "USD", rate_date: "2026-07-24", rate_to_base: "16.200000" } });
      return;
    }
    if (path.endsWith("/products/page")) {
      const items = overrides.products ?? [product];
      await route.fulfill({ json: { items, total: items.length, offset: 0, limit: 25 } });
      return;
    }
    if (path.endsWith("/products/options")) {
      await route.fulfill({ json: overrides.products ?? [product] });
      return;
    }
    if (path.endsWith("/products/group-counts")) {
      const items = overrides.products ?? [product];
      const counts = new Map<number, number>();
      items.forEach((item) => {
        if (typeof item.group_id !== "number") return;
        counts.set(item.group_id, (counts.get(item.group_id) ?? 0) + 1);
      });
      await route.fulfill({ json: { total: items.length, items: [...counts].map(([group_id, count]) => ({ group_id, count })) } });
      return;
    }
    if (path.endsWith("/products")) {
      await route.fulfill({ json: overrides.products ?? [product] });
      return;
    }
    if (path.endsWith("/product-groups")) {
      await route.fulfill({ json: overrides.productGroups ?? [] });
      return;
    }
    if (path.endsWith("/partners/page")) {
      await route.fulfill({ json: { items: [supplier, customer], total: 2, offset: 0, limit: 25 } });
      return;
    }
    if (path.endsWith("/partners/options")) {
      await route.fulfill({ json: [supplier, customer] });
      return;
    }
    if (path.endsWith("/partners") && request.method() === "POST") {
      const payload = request.postDataJSON() as Record<string, unknown>;
      overrides.onCreatePartner?.(payload);
      await route.fulfill({ json: { ...payload, id: 9 } });
      return;
    }
    if (/\/partners\/\d+$/.test(path)) {
      await route.fulfill({ json: path.endsWith("/2") ? customer : supplier });
      return;
    }
    if (path.endsWith("/partners")) {
      await route.fulfill({ json: [supplier, customer] });
      return;
    }
    if (path.endsWith("/warehouses")) {
      await route.fulfill({ json: [warehouse] });
      return;
    }
    if (path.includes("/stock/balances")) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith("/cash/book/page")) {
      await route.fulfill({
        json: {
          items: [],
          total: 0,
          offset: 0,
          limit: 25,
          current_balance: "0.00",
          page_opening_balance: "0.00",
          page_closing_balance: "0.00",
        },
      });
      return;
    }
    if (path.endsWith("/cash/balance")) {
      await route.fulfill({ json: { balance: "0.00" } });
      return;
    }
    if (path.endsWith("/payments/page")) {
      const search = new URL(request.url()).searchParams.get("search")?.toLowerCase() ?? "";
      const status = new URL(request.url()).searchParams.get("status") ?? "";
      const rows = (overrides.paymentRows ?? []).filter((item) => (!search || String(item.partner_name).toLowerCase().includes(search)) && (!status || item.status === status));
      await route.fulfill({ json: { items: rows, total: rows.length, offset: 0, limit: 25 } });
      return;
    }
    if (path.endsWith("/logistics/tasks")) {
      await route.fulfill({ json: overrides.warehouseTasks ?? [] });
      return;
    }

    await route.fulfill({ json: [] });
  });
}

test("SEC-06: временный пароль требуется сменить до начала работы", async ({ page }) => {
  let changed = false;
  await mockManagerApi(page, {
    currentUser: { ...manager, must_change_password: true },
    onChangePassword: () => { changed = true; },
  });

  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("manager@example.com");
  await page.getByLabel("Пароль").fill("temporary-password");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page.getByRole("heading", { name: "Задайте новый пароль" })).toBeVisible();
  await page.getByLabel("Текущий пароль").fill("temporary-password");
  await page.getByLabel("Новый пароль", { exact: true }).fill("new-secure-password");
  await page.getByLabel("Подтвердите пароль").fill("new-secure-password");
  await page.getByRole("button", { name: "Сменить пароль" }).click();

  await expect(page.getByTestId("header-user")).toBeVisible();
  expect(changed).toBe(true);
});

async function loginAsManager(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("manager@example.com");
  await page.getByLabel("Пароль").fill("manager123");
  await page.getByRole("button", { name: "Войти" }).click();
  const headerUser = page.getByTestId("header-user");
  await expect(headerUser).toBeVisible();
  await expect(headerUser).toContainText("Тестовый менеджер:");
  await expect(headerUser).toContainText("Менеджер");
}

test("M01: менеджер входит и видит только разрешенные разделы", async ({ page }) => {
  await mockManagerApi(page);
  await loginAsManager(page);

  const navigation = page.locator(".sidebar-nav");
  await expect(navigation.getByRole("link", { name: "Документы" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Складской учет" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Оплаты" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Касса" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Настройки" })).toHaveCount(0);

  const quickActions = page.getByRole("region", { name: "Быстрые действия менеджера" });
  await expect(quickActions.getByRole("link", { name: "Новая продажа" })).toHaveAttribute("href", "/documents?create=outgoing");
  await expect(quickActions.getByRole("link", { name: "Новый приход" })).toHaveAttribute("href", "/documents?create=incoming");
  await expect(quickActions.getByRole("link", { name: "Принять оплату" })).toHaveAttribute("href", "/payments?create=customer_payment");
  await expect(quickActions.getByRole("link", { name: "Записать расход" })).toHaveAttribute("href", "/cash?create=cash_out");

  await quickActions.getByRole("link", { name: "Новая продажа" }).click();
  await expect(page.getByTestId("draft-document-type")).toHaveValue("outgoing");
  await expect(page.getByTestId("draft-document-warehouse")).toHaveValue("1");
});

test("M01a: показатель открывает журнал с тем же статусом и периодом", async ({ page }) => {
  await mockManagerApi(page);
  await loginAsManager(page);

  await page.getByRole("link", { name: /Черновики: .*Открыть список/ }).click();
  await expect(page).toHaveURL((url) => url.pathname === "/documents" && url.searchParams.get("status") === "draft" && /^\d{4}-\d{2}-\d{2}$/.test(url.searchParams.get("date_from") ?? ""));
  await expect(page.getByRole("combobox", { name: "Фильтр: Статус" })).toHaveValue("draft");
  await expect(page.getByLabel("С даты")).not.toHaveValue("");
  await expect(page.getByRole("navigation", { name: "Команды раздела" }).getByRole("link", { name: "Документы" })).toBeVisible();
});

test("M02: валютный приход показывает необходимость пересмотра цены", async ({ page }) => {
  await mockManagerApi(page, {
    document: {
      id: 42,
      document_type: "incoming",
      number: "IN-000042",
      document_date: "2026-07-24",
      status: "draft",
      partner_id: supplier.id,
      partner_name: supplier.name,
      warehouse_id: warehouse.id,
      warehouse_name: warehouse.name,
      destination_warehouse_id: null,
      destination_warehouse_name: null,
      total_amount: "0.00",
      foreign_total_amount: "0.00",
      currency_code: "RUB_PMR",
      exchange_rate: "1.000000",
      note: null,
      lines: [],
    },
  });
  await loginAsManager(page);
  await page.goto("/documents/42", { waitUntil: "domcontentloaded" });

  await page.getByTestId("document-currency").selectOption("USD");
  await expect(page.getByTestId("document-exchange-rate")).toHaveValue("16.200000");
  await page.getByTestId("document-product").fill("TEST-1");
  await expect(page.getByRole("option", { name: /Тестовый товар.*TEST-1/ })).toBeVisible();
  await page.getByTestId("document-product").press("ArrowDown");
  await page.getByTestId("document-product").press("Enter");
  await expect(page.getByTestId("document-product")).toHaveValue(/Тестовый товар/);
  await page.getByTestId("document-line-price").fill("10");

  await expect(page.getByText("Пересмотрите цену реализации.")).toBeVisible();
  await expect(page.getByText(/первая проведённая закупка/i)).toBeVisible();
  await expect(page.getByText(/162\.00/)).toBeVisible();
});

test("M03: документ и навигация доступны на узком экране", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockManagerApi(page, {
    document: {
      id: 42,
      document_type: "outgoing",
      number: "OUT-000042",
      document_date: "2026-07-24",
      status: "draft",
      partner_id: customer.id,
      partner_name: customer.name,
      warehouse_id: warehouse.id,
      warehouse_name: warehouse.name,
      destination_warehouse_id: null,
      destination_warehouse_name: null,
      total_amount: "500.00",
      foreign_total_amount: null,
      currency_code: "RUB_PMR",
      exchange_rate: "1.000000",
      note: null,
      lines: [{ id: 1, document_id: 42, product_id: product.id, product_name: product.name, quantity: "5.000", price: "100.00", line_total: "500.00" }],
    },
  });
  await loginAsManager(page);
  await page.goto("/documents/42", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /OUT-000042/ })).toBeVisible();
  await expect(page.getByRole("region", { name: "Реквизиты документа" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Товары и суммы" })).toBeVisible();
  await page.getByRole("button", { name: "Открыть меню" }).click();
  await expect(page.getByRole("navigation", { name: "Команды раздела" }).getByRole("link", { name: "Документы" })).toBeVisible();
  await page.getByRole("button", { name: "Закрыть меню" }).first().click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("M03a: журнал документов показывает фильтры и раскрывает создание", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockManagerApi(page);
  await loginAsManager(page);
  await page.goto("/documents", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("region", { name: "Журнал документов" })).toBeVisible();
  await expect(page.getByTestId("draft-document-type")).toHaveCount(0);
  await page.getByRole("button", { name: "Создать документ" }).first().click();
  await expect(page.getByTestId("draft-document-type")).toBeVisible();
  await expect(page.getByTestId("draft-document-warehouse")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("M03b: документ показывает ошибку поля и предупреждает о несохранённых изменениях", async ({ page }) => {
  await mockManagerApi(page, {
    document: {
      id: 42,
      document_type: "outgoing",
      number: "OUT-000042",
      document_date: "2026-07-24",
      status: "draft",
      partner_id: customer.id,
      partner_name: customer.name,
      warehouse_id: warehouse.id,
      warehouse_name: warehouse.name,
      destination_warehouse_id: null,
      destination_warehouse_name: null,
      total_amount: "0.00",
      foreign_total_amount: null,
      currency_code: "RUB_PMR",
      exchange_rate: "1.000000",
      note: null,
      lines: [],
    },
  });
  await loginAsManager(page);
  await page.goto("/documents/42", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Склад", { exact: true }).selectOption("");
  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Выберите склад").first()).toBeVisible();
  await page.getByLabel("Склад", { exact: true }).selectOption(String(warehouse.id));
  await page.getByLabel("Примечание").fill("Проверить перед проведением");
  await expect(page.getByText("Есть несохранённые изменения")).toBeVisible();

  await page.evaluate(() => {
    let attempts = 0;
    window.confirm = () => ++attempts > 1;
  });
  await page.getByRole("link", { name: /к документам/i }).click();
  await expect(page).toHaveURL(/\/documents\/42$/);
  await page.getByRole("link", { name: /к документам/i }).click();
  await expect(page).toHaveURL((url) => url.pathname === "/documents");
});

test("M03c: журналы оплат и кассы открывают форму по команде", async ({ page }) => {
  await mockManagerApi(page);
  await loginAsManager(page);

  await page.goto("/payments", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("payment-save")).toHaveCount(0);
  await page.getByRole("button", { name: "Создать оплату" }).click();
  await expect(page.getByTestId("payment-save")).toBeVisible();
  await page.getByTestId("payment-save").click();
  await expect(page.getByText("Выберите контрагента").last()).toBeVisible();
  await page.getByRole("button", { name: "Отменить" }).last().click();
  await expect(page.getByTestId("payment-save")).toHaveCount(0);
  await page.goto("/payments?create=supplier_payment", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("payment-type")).toHaveValue("supplier_payment");

  await page.goto("/cash", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "Создать операцию" })).toHaveCount(1);
  await page.goto("/cash?create=cash_out", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "Создать операцию" })).toHaveCount(2);
  await page.getByRole("button", { name: "Создать операцию" }).last().click();
  await expect(page.getByText("Введите сумму больше нуля")).toBeVisible();
});

test("M03d: работник склада видит свои задания и мобильную карточку позиции", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockManagerApi(page, {
    currentUser: {
      ...manager,
      id: 3,
      role_names: ["warehouse_worker"],
      permissions: ["logistics.read", "logistics.process"],
      warehouse_names: [warehouse.name],
    },
    warehouseTasks: [{
      id: 7,
      document_id: 42,
      document_number: "OUT-000042",
      document_date: "2026-07-24",
      document_type: "outgoing",
      posting_version: 1,
      warehouse_id: warehouse.id,
      warehouse_name: warehouse.name,
      task_type: "pick",
      status: "in_progress",
      created_at: "2026-07-24T10:00:00Z",
      lines: [{ id: 8, product_id: product.id, product_name: product.name, expected_quantity: "2", actual_quantity: null, status: "pending", comment: null, sale_price: "100.00", sale_total: "200.00" }],
      events: [],
    }],
  });
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("manager@example.com");
  await page.getByLabel("Пароль").fill("manager123");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByTestId("header-user")).toBeVisible();
  await expect(page.getByRole("link", { name: "Задания склада" }).first()).toBeVisible();
  await expect(page.getByText("Деньги и документы")).toHaveCount(0);
  await page.goto("/logistics", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("task-line-actual-8")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("CAT-02: ИНН сохраняется, фильтры сбрасываются", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let created: Record<string, unknown> | null = null;
  await mockManagerApi(page, { onCreatePartner: (payload) => { created = payload; } });
  await loginAsManager(page);
  await page.goto("/partners", { waitUntil: "domcontentloaded" });

  await expect(page.getByLabel("ИНН")).toHaveCount(0);
  await page.getByRole("button", { name: "Создать" }).first().click();
  await page.getByLabel("Наименование").fill("Длинное название тестового контрагента");
  await page.getByLabel("ИНН").fill("TIN-12345");
  await page.getByRole("button", { name: "Создать" }).last().click();
  await expect.poll(() => created?.tax_id).toBe("TIN-12345");
  await expect(page.getByLabel("ИНН")).toHaveCount(0);

  await page.getByRole("combobox", { name: "Фильтр: Тип контрагента" }).selectOption("customer");
  await expect(page.getByRole("button", { name: "Сбросить фильтры" })).toBeVisible();
  await page.getByRole("button", { name: "Сбросить фильтры" }).click();
  await expect(page.getByRole("combobox", { name: "Фильтр: Тип контрагента" })).toHaveValue("");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("FIN-01: поиск и фильтр оплат обращаются к журналу", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockManagerApi(page, { paymentRows: [{
    id: 77,
    partner_id: customer.id,
    partner_name: "Удалённый клиент",
    payment_date: "2026-07-24",
    payment_type: "customer_payment",
    status: "posted",
    amount: "500.00",
    allocated_amount: "0.00",
    unallocated_amount: "500.00",
    method: "cash",
    allocations: [],
  }] });
  await loginAsManager(page);
  await page.goto("/payments", { waitUntil: "domcontentloaded" });
  await page.getByRole("textbox", { name: "Поиск" }).fill("Удалённый");
  await expect(page.getByText("Удалённый клиент")).toBeVisible();
  await page.getByRole("combobox", { name: "Фильтр: Статус" }).selectOption("draft");
  await expect(page.getByText("Удалённый клиент")).toHaveCount(0);
  await page.getByRole("button", { name: "Сбросить фильтры" }).click();
  await expect(page.getByText("Удалённый клиент")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByText("Ещё").click();
  await page.getByRole("button", { name: "Отменить" }).last().click();
  await expect(page.getByRole("dialog", { name: "Подтверждение действия" })).toContainText("№77");
  await page.getByRole("dialog", { name: "Подтверждение действия" }).getByRole("button", { name: "Не выполнять" }).click();
});

test("M04: нехватка остатка не проводит расходный документ", async ({ page }) => {
  let postAttempted = false;
  await mockManagerApi(page, {
    document: {
      id: 42,
      document_type: "outgoing",
      number: "OUT-000042",
      document_date: "2026-07-24",
      status: "draft",
      partner_id: customer.id,
      partner_name: customer.name,
      warehouse_id: warehouse.id,
      warehouse_name: warehouse.name,
      destination_warehouse_id: null,
      destination_warehouse_name: null,
      total_amount: "500.00",
      foreign_total_amount: "500.00",
      currency_code: "RUB_PMR",
      exchange_rate: "1.000000",
      note: null,
      lines: [{ id: 1, document_id: 42, product_id: product.id, product_name: product.name, quantity: "5.000", price: "100.00", line_total: "500.00" }],
    },
    onPostDocument: () => {
      postAttempted = true;
    },
  });
  await loginAsManager(page);
  await page.goto("/documents/42", { waitUntil: "domcontentloaded" });

  await page.getByTestId("document-post").click();
  await expect(page.getByRole("dialog", { name: "Подтверждение действия" })).toContainText("OUT-000042");
  await page.getByRole("dialog", { name: "Подтверждение действия" }).getByRole("button", { name: "Провести" }).click();

  await expect(page.getByText("Недостаточно остатка", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Черновик", { exact: true })).toBeVisible();
  expect(postAttempted).toBe(true);
});

test("CAT-01: каталог сохраняет вложенные категории и контроль цены", async ({ page }) => {
  await mockManagerApi(page, {
    productGroups: [
      { id: 10, name: "Продукты", parent_id: null, parent_name: null, created_at: "2026-10-10T10:00:00Z", updated_at: "2026-10-10T10:00:00Z" },
      { id: 11, name: "Напитки", parent_id: 10, parent_name: "Продукты", created_at: "2026-10-10T10:00:00Z", updated_at: "2026-10-10T10:00:00Z" },
      { id: 12, name: "Газированные", parent_id: 11, parent_name: "Напитки", created_at: "2026-10-10T10:00:00Z", updated_at: "2026-10-10T10:00:00Z" },
    ],
    products: [
      {
        id: 101,
        sku: "DRINK-1",
        name: "Напиток тестовый",
        group_id: 12,
        group_name: "Газированные",
        base_price: "100.00",
        current_cost: "95.00",
        current_cost_source: "purchase",
        current_cost_date: "2026-10-10",
        markup_percent: "5.26",
        minimum_sale_price: "104.50",
        price_review_required: true,
        is_active: true,
      },
    ],
  });
  await loginAsManager(page);
  await page.goto("/products", { waitUntil: "domcontentloaded" });

  const categoryTree = page.locator(".category-tree");
  await expect(categoryTree.getByText("Продукты", { exact: true })).toBeVisible();
  await categoryTree.getByRole("button", { name: /Продукты/ }).click();
  await expect(categoryTree.getByText("Напитки", { exact: true })).toBeVisible();
  await categoryTree.getByRole("button", { name: /Напитки/ }).click();
  await expect(categoryTree.getByText("Газированные", { exact: true })).toBeVisible();
  await categoryTree.getByRole("button", { name: /Газированные/ }).click();

  await expect(page.getByRole("columnheader", { name: "Себестоимость" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Наценка" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Контроль цены" })).toBeVisible();
  await expect(page.getByText("Напиток тестовый", { exact: true })).toBeVisible();
  await expect(page.getByText("Газированные", { exact: true }).last()).toBeVisible();
  await expect(page.getByText("Пересмотреть цену: 104.50", { exact: true })).toBeVisible();
});
