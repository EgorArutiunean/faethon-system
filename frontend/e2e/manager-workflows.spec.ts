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
  await page.getByTestId("document-product").selectOption("1");
  await page.getByTestId("document-line-price").fill("10");

  await expect(page.getByText("Пересмотрите цену реализации.")).toBeVisible();
  await expect(page.getByText(/первая проведённая закупка/i)).toBeVisible();
  await expect(page.getByText(/162\.00/)).toBeVisible();
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

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();

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
        latest_purchase_cost: "95.00",
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

  await expect(page.getByRole("columnheader", { name: "Последняя себестоимость" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Наценка" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Контроль цены" })).toBeVisible();
  await expect(page.getByText("Напиток тестовый", { exact: true })).toBeVisible();
  await expect(page.getByText("Газированные", { exact: true }).last()).toBeVisible();
  await expect(page.getByText("Пересмотреть цену: 104.50", { exact: true })).toBeVisible();
});
