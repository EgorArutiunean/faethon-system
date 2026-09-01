import { APIRequestContext, expect, Page, request, test } from "@playwright/test";

const apiBaseUrl = "http://127.0.0.1:18000/api/v1/";

function relativeApiPath(path: string) {
  return path.replace(/^\//, "");
}

type SeededSaleData = {
  token: string;
  productId: number;
  warehouseId: number;
  supplierId: number;
  customerId: number;
  incomingId: number;
};

async function postJson(api: APIRequestContext, path: string, token: string, data: Record<string, unknown>) {
  const response = await api.post(relativeApiPath(path), {
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
  if (!response.ok()) {
    throw new Error(`${path}: ${response.status()} ${await response.text()}`);
  }
  return response.json();
}

async function loginToken(api: APIRequestContext, email: string, password: string) {
  const response = await api.post("auth/login", { data: { email, password } });
  if (!response.ok()) {
    throw new Error(`auth/login: ${response.status()} ${await response.text()}`);
  }
  return (await response.json()).access_token as string;
}

async function prepareStock(key = "SALE"): Promise<SeededSaleData> {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const token = await loginToken(api, "manager@example.com", "manager123");

  const warehouse = await postJson(api, "/warehouses", token, {
    code: `E2E-${key}-MAIN`,
    name: "E2E Основной склад",
    address: "Тестовый адрес",
  });
  const product = await postJson(api, "/products", token, {
    sku: `E2E-${key}-PRODUCT`,
    name: "E2E Контрольный товар",
    base_price: "150.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", token, {
    code: `E2E-${key}-SUPPLIER`,
    name: "E2E Поставщик",
    partner_type: "supplier",
    is_active: true,
  });
  const customer = await postJson(api, "/partners", token, {
    code: `E2E-${key}-CUSTOMER`,
    name: "E2E Клиент",
    partner_type: "customer",
    is_active: true,
  });
  const incoming = await postJson(api, "/documents", token, {
    document_type: "incoming",
    document_date: "2026-07-24",
    status: "draft",
    partner_id: supplier.id,
    warehouse_id: warehouse.id,
    total_amount: "0",
  });
  await postJson(api, `/documents/${incoming.id}/lines`, token, {
    product_id: product.id,
    quantity: "5",
    price: "80.00",
  });
  await postJson(api, `/documents/${incoming.id}/post`, token, {});

  const initialStock = await api.get(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(initialStock.ok()).toBeTruthy();
  expect((await initialStock.json())[0].quantity).toBe("5.000");
  await api.dispose();

  return {
    token,
    productId: product.id,
    warehouseId: warehouse.id,
    supplierId: supplier.id,
    customerId: customer.id,
    incomingId: incoming.id,
  };
}

async function loginAsManager(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("manager@example.com");
  await page.getByLabel("Пароль").fill("manager123");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Роль: Менеджер")).toBeVisible();
}

async function loginAsCashier(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("cashier@example.com");
  await page.getByLabel("Пароль").fill("cashier123");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Роль: Кассир")).toBeVisible();
}

async function loginAsLogist(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("logist-e2e@example.com");
  await page.getByLabel("Пароль").fill("logist123");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Роль: Логист")).toBeVisible();
}

async function createDraftThroughUi(
  page: Page,
  documentType: "incoming" | "outgoing" | "transfer",
  warehouseId: number,
  partnerId?: number,
  destinationWarehouseId?: number,
) {
  await page.goto("/documents", { waitUntil: "domcontentloaded" });
  await page.getByTestId("draft-document-type").selectOption(documentType);
  await page.getByTestId("draft-document-warehouse").selectOption(String(warehouseId));
  if (destinationWarehouseId) {
    await page.getByTestId("draft-document-destination").selectOption(String(destinationWarehouseId));
  }
  if (partnerId) {
    await page.getByTestId("draft-document-partner").selectOption(String(partnerId));
  }
  await page.getByTestId("draft-document-create").click();
  await expect(page).toHaveURL(/\/documents\/\d+$/);
  const documentId = Number(page.url().match(/\/documents\/(\d+)$/)?.[1]);
  expect(documentId).toBeGreaterThan(0);
  return documentId;
}

async function createAndPostPaymentThroughUi(
  page: Page,
  api: APIRequestContext,
  token: string,
  paymentType: "customer_payment" | "supplier_payment",
  partnerId: number,
  documentId: number,
  amount: string,
) {
  if (!new URL(page.url()).pathname.endsWith("/payments")) {
    await page.goto("/payments", { waitUntil: "domcontentloaded" });
  }
  await page.getByTestId("payment-type").selectOption(paymentType);
  await page.getByTestId("payment-partner").selectOption(String(partnerId));
  await page.getByTestId("payment-document").selectOption(String(documentId));
  await page.getByTestId("payment-amount").fill(amount);
  await page.getByTestId("payment-save").click();

  let paymentId = 0;
  await expect.poll(async () => {
    const response = await api.get("payments", { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok()) return 0;
    const payments = await response.json();
    const payment = payments.find((row: {
      partner_id: number;
      document_id: number | null;
      payment_type: string;
      amount: string;
      status: string;
    }) => (
      row.partner_id === partnerId
      && row.document_id === documentId
      && row.payment_type === paymentType
      && Number(row.amount) === Number(amount)
      && row.status === "draft"
    ));
    paymentId = payment?.id ?? 0;
    return paymentId;
  }).toBeGreaterThan(0);

  await page.getByTestId(`payment-post-${paymentId}`).click();
  await expect.poll(async () => {
    const response = await api.get(`payments/${paymentId}`, { headers: { Authorization: `Bearer ${token}` } });
    return response.ok() ? (await response.json()).status : "";
  }).toBe("posted");
  return paymentId;
}

test("M03: продажа через интерфейс согласует документ, склад, долг и отчет", async ({ page }) => {
  const seeded = await prepareStock();
  await loginAsManager(page);
  const documentId = await createDraftThroughUi(page, "outgoing", seeded.warehouseId, seeded.customerId);
  await page.getByTestId("document-product").selectOption(String(seeded.productId));
  await page.getByTestId("document-line-quantity").fill("2");
  await page.getByTestId("document-line-price").fill("150");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Контрольный товар" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("Проведён", { exact: true })).toBeVisible();
  await expect(page.getByTestId("document-post")).toBeDisabled();

  const api = await request.newContext({
    baseURL: apiBaseUrl,
    extraHTTPHeaders: { Authorization: `Bearer ${seeded.token}` },
  });
  const [documentResponse, stockResponse, debtResponse, registerResponse] = await Promise.all([
    api.get(`documents/${documentId}`),
    api.get(`stock/balances?warehouse_id=${seeded.warehouseId}&product_id=${seeded.productId}`),
    api.get(`partners/${seeded.customerId}/balance`),
    api.get(`reports/documents-register?partner_id=${seeded.customerId}&status=posted`),
  ]);

  expect(documentResponse.ok()).toBeTruthy();
  expect(stockResponse.ok()).toBeTruthy();
  expect(debtResponse.ok()).toBeTruthy();
  expect(registerResponse.ok()).toBeTruthy();

  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  const debt = await debtResponse.json();
  const register = await registerResponse.json();
  expect(document.status).toBe("posted");
  expect(document.total_amount).toBe("300.00");
  expect(stock[0].quantity).toBe("3.000");
  expect(debt.balance).toBe("300.00");
  expect(register.total_amount).toBe("300.00");
  expect(register.rows).toEqual(expect.arrayContaining([expect.objectContaining({ id: documentId, total_amount: "300.00" })]));
  await api.dispose();
});

test("M08: менеджер исправляет проведенный приход с полной историей", async ({ page }) => {
  const seeded = await prepareStock("REPOST");
  await loginAsManager(page);
  await page.goto(`/documents/${seeded.incomingId}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Проведён", { exact: true })).toBeVisible();
  await expect(page.getByTestId("document-posting-version")).toHaveText("v1");

  await page.getByTestId("document-correction-start").click();
  await page.getByTestId("document-correction-reason").fill("Уточнено фактическое количество при приёмке");
  await page.getByRole("button", { name: "Изменить строку" }).click();
  await page.getByTestId("document-line-quantity").fill("7");
  await page.getByTestId("document-line-price").fill("80");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Контрольный товар" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-correction-apply").click();
  await expect(page.getByTestId("document-posting-version")).toHaveText("v2");
  await expect(page.getByText("Уточнено фактическое количество при приёмке", { exact: true })).toBeVisible();

  const api = await request.newContext({
    baseURL: apiBaseUrl,
    extraHTTPHeaders: { Authorization: `Bearer ${seeded.token}` },
  });
  const [documentResponse, stockResponse, debtResponse, revisionsResponse, movementsResponse] = await Promise.all([
    api.get(`documents/${seeded.incomingId}`),
    api.get(`stock/balances?warehouse_id=${seeded.warehouseId}&product_id=${seeded.productId}`),
    api.get(`partners/${seeded.supplierId}/balance`),
    api.get(`documents/${seeded.incomingId}/revisions`),
    api.get(`stock/movements?document_id=${seeded.incomingId}`),
  ]);
  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  const debt = await debtResponse.json();
  const revisions = await revisionsResponse.json();
  const movements = await movementsResponse.json();
  expect(document.posting_version).toBe(2);
  expect(document.lines[0].quantity).toBe("7.000");
  expect(document.total_amount).toBe("560.00");
  expect(stock[0].quantity).toBe("7.000");
  expect(debt.balance).toBe("-560.00");
  expect(revisions.map((revision: { version: number }) => revision.version)).toEqual([2, 1]);
  expect(movements).toHaveLength(3);
  await api.dispose();
});

test("M02: валютный приход фиксирует курс, суммы и остаток в PostgreSQL", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const managerToken = await loginToken(api, "manager@example.com", "manager123");
  const adminToken = await loginToken(api, "admin@example.com", "admin123");
  const today = new Date().toISOString().slice(0, 10);

  const warehouse = await postJson(api, "/warehouses", managerToken, {
    code: "E2E-FX-WAREHOUSE",
    name: "E2E FX Warehouse",
  });
  const product = await postJson(api, "/products", managerToken, {
    sku: "E2E-FX-PRODUCT",
    name: "E2E FX Product",
    base_price: "100.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", managerToken, {
    code: "E2E-FX-SUPPLIER",
    name: "E2E FX Supplier",
    partner_type: "supplier",
    is_active: true,
  });
  await postJson(api, "/currencies/rates", adminToken, {
    currency_code: "USD",
    rate_date: today,
    rate_to_base: "16.200000",
    note: "M02",
  });

  await loginAsManager(page);
  const documentId = await createDraftThroughUi(page, "incoming", warehouse.id, supplier.id);
  await page.getByTestId("document-currency").selectOption("USD");
  await expect.poll(async () => Number(await page.getByTestId("document-exchange-rate").inputValue())).toBe(16.2);
  await page.getByTestId("document-product").selectOption(String(product.id));
  await page.getByTestId("document-line-quantity").fill("2");
  await page.getByTestId("document-line-price").fill("10");
  await expect(page.getByText("\u041f\u0435\u0440\u0435\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u0446\u0435\u043d\u0443 \u0440\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438.")).toBeVisible();
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E FX Product" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("\u041f\u0440\u043e\u0432\u0435\u0434\u0451\u043d", { exact: true })).toBeVisible();

  const [documentResponse, stockResponse, productsResponse] = await Promise.all([
    api.get(`documents/${documentId}`, { headers: { Authorization: `Bearer ${managerToken}` } }),
    api.get(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, {
      headers: { Authorization: `Bearer ${managerToken}` },
    }),
    api.get("products", { headers: { Authorization: `Bearer ${managerToken}` } }),
  ]);
  expect(documentResponse.ok()).toBeTruthy();
  expect(stockResponse.ok()).toBeTruthy();
  expect(productsResponse.ok()).toBeTruthy();
  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  const pricedProduct = (await productsResponse.json()).find((row: { id: number }) => row.id === product.id);
  expect(document.status).toBe("posted");
  expect(document.currency_code).toBe("USD");
  expect(document.exchange_rate).toBe("16.200000");
  expect(document.foreign_total_amount).toBe("20.00");
  expect(document.total_amount).toBe("324.00");
  expect(stock[0].quantity).toBe("2.000");
  expect(pricedProduct.latest_purchase_cost).toBe("162.00");
  expect(pricedProduct.markup_percent).toBe("-38.27");
  expect(pricedProduct.minimum_sale_price).toBe("178.20");
  expect(pricedProduct.price_review_required).toBe(true);

  await page.goto("/products", { waitUntil: "domcontentloaded" });
  const productRow = page.getByRole("row").filter({ hasText: "E2E FX Product" });
  await expect(productRow.getByText("Пересмотреть цену", { exact: false })).toBeVisible();
  await api.dispose();
});

test("M04: неуспешный расход не меняет остаток и долг", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const token = await loginToken(api, "manager@example.com", "manager123");
  const warehouse = await postJson(api, "/warehouses", token, {
    code: "E2E-EMPTY-WAREHOUSE",
    name: "E2E Empty Warehouse",
  });
  const product = await postJson(api, "/products", token, {
    sku: "E2E-EMPTY-PRODUCT",
    name: "E2E Empty Product",
    base_price: "100.00",
    is_active: true,
  });
  const customer = await postJson(api, "/partners", token, {
    code: "E2E-EMPTY-CUSTOMER",
    name: "E2E Empty Customer",
    partner_type: "customer",
    is_active: true,
  });

  await loginAsManager(page);
  const documentId = await createDraftThroughUi(page, "outgoing", warehouse.id, customer.id);
  await page.getByTestId("document-product").selectOption(String(product.id));
  await page.getByTestId("document-line-quantity").fill("1");
  await page.getByTestId("document-line-price").fill("100");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Empty Product" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u043e\u0441\u0442\u0430\u0442\u043a\u0430", { exact: true }).first()).toBeVisible();

  const headers = { Authorization: `Bearer ${token}` };
  const [documentResponse, stockResponse, debtResponse, registerResponse] = await Promise.all([
    api.get(`documents/${documentId}`, { headers }),
    api.get(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, { headers }),
    api.get(`partners/${customer.id}/balance`, { headers }),
    api.get(`reports/documents-register?partner_id=${customer.id}&status=posted`, { headers }),
  ]);
  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  const debt = await debtResponse.json();
  const register = await registerResponse.json();
  expect(document.status).toBe("draft");
  expect(stock).toEqual([]);
  expect(debt.balance).toBe("0");
  expect(register.rows).toEqual([]);
  expect(register.total_amount).toBe("0");
  await api.dispose();
});

test("M05: перемещение сохраняет общий остаток и создает два движения", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const token = await loginToken(api, "manager@example.com", "manager123");
  const source = await postJson(api, "/warehouses", token, {
    code: "E2E-TRANSFER-SOURCE",
    name: "E2E Transfer Source",
  });
  const destination = await postJson(api, "/warehouses", token, {
    code: "E2E-TRANSFER-DESTINATION",
    name: "E2E Transfer Destination",
  });
  const product = await postJson(api, "/products", token, {
    sku: "E2E-TRANSFER-PRODUCT",
    name: "E2E Transfer Product",
    base_price: "50.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", token, {
    code: "E2E-TRANSFER-SUPPLIER",
    name: "E2E Transfer Supplier",
    partner_type: "supplier",
    is_active: true,
  });
  const incoming = await postJson(api, "/documents", token, {
    document_type: "incoming",
    document_date: "2026-07-24",
    partner_id: supplier.id,
    warehouse_id: source.id,
  });
  await postJson(api, `/documents/${incoming.id}/lines`, token, {
    product_id: product.id,
    quantity: "5",
    price: "40.00",
  });
  await postJson(api, `/documents/${incoming.id}/post`, token, {});

  await loginAsManager(page);
  const transferId = await createDraftThroughUi(page, "transfer", source.id, undefined, destination.id);
  await page.getByTestId("document-product").selectOption(String(product.id));
  await page.getByTestId("document-line-quantity").fill("2");
  await page.getByTestId("document-line-price").fill("50");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Transfer Product" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("\u041f\u0440\u043e\u0432\u0435\u0434\u0451\u043d", { exact: true })).toBeVisible();

  const headers = { Authorization: `Bearer ${token}` };
  const [sourceResponse, destinationResponse, movementsResponse, reportResponse] = await Promise.all([
    api.get(`stock/balances?warehouse_id=${source.id}&product_id=${product.id}`, { headers }),
    api.get(`stock/balances?warehouse_id=${destination.id}&product_id=${product.id}`, { headers }),
    api.get(`stock/movements?document_id=${transferId}`, { headers }),
    api.get(`reports/stock-balances?product_id=${product.id}`, { headers }),
  ]);
  const sourceStock = await sourceResponse.json();
  const destinationStock = await destinationResponse.json();
  const movements = await movementsResponse.json();
  const report = await reportResponse.json();
  expect(sourceStock[0].quantity).toBe("3.000");
  expect(destinationStock[0].quantity).toBe("2.000");
  expect(movements).toHaveLength(2);
  expect(movements.map((row: { quantity_delta: string }) => row.quantity_delta).sort()).toEqual(["-2.000", "2.000"]);
  expect(report.total_quantity).toBe("5.000");
  await api.dispose();
});

test("M06: partial customer payment updates debt, cash and statement", async ({ page }) => {
  const seeded = await prepareStock("M06");
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const cashierToken = await loginToken(api, "cashier@example.com", "cashier123");
  const outgoing = await postJson(api, "/documents", seeded.token, {
    document_type: "outgoing",
    document_date: "2026-07-24",
    partner_id: seeded.customerId,
    warehouse_id: seeded.warehouseId,
  });
  await postJson(api, `/documents/${outgoing.id}/lines`, seeded.token, {
    product_id: seeded.productId,
    quantity: "2",
    price: "150.00",
  });
  await postJson(api, `/documents/${outgoing.id}/post`, seeded.token, {});

  const headers = { Authorization: `Bearer ${cashierToken}` };
  const initialCash = Number((await (await api.get("cash/balance", { headers })).json()).balance);
  await loginAsCashier(page);
  const paymentId = await createAndPostPaymentThroughUi(
    page,
    api,
    cashierToken,
    "customer_payment",
    seeded.customerId,
    outgoing.id,
    "120.00",
  );

  const [balanceResponse, cashResponse, statementResponse, cashBookResponse] = await Promise.all([
    api.get(`partners/${seeded.customerId}/balance`, { headers }),
    api.get("cash/balance", { headers }),
    api.get(`partners/${seeded.customerId}/statement`, { headers }),
    api.get("cash/book", { headers }),
  ]);
  const balance = await balanceResponse.json();
  const cash = await cashResponse.json();
  const statement = await statementResponse.json();
  const cashBook = await cashBookResponse.json();

  expect(balance.balance).toBe("180.00");
  expect(Number(cash.balance)).toBe(initialCash + 120);
  expect(statement).toEqual(expect.arrayContaining([
    expect.objectContaining({
      source_type: "payment",
      source_id: paymentId,
      credit: "120.00",
      balance: "180.00",
    }),
  ]));
  expect(cashBook).toEqual(expect.arrayContaining([
    expect.objectContaining({
      payment_id: paymentId,
      document_id: outgoing.id,
      operation_type: "cash_in",
      amount: "120.00",
      status: "posted",
    }),
  ]));
  await api.dispose();
});

test("M07: supplier partial, full and overpayment update debt and cash", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const managerToken = await loginToken(api, "manager@example.com", "manager123");
  const cashierToken = await loginToken(api, "cashier@example.com", "cashier123");
  const warehouse = await postJson(api, "/warehouses", managerToken, {
    code: "E2E-PAYMENT-WAREHOUSE",
    name: "E2E Payment Warehouse",
  });
  const product = await postJson(api, "/products", managerToken, {
    sku: "E2E-PAYMENT-PRODUCT",
    name: "E2E Payment Product",
    base_price: "500.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", managerToken, {
    code: "E2E-PAYMENT-SUPPLIER",
    name: "E2E Payment Supplier",
    partner_type: "supplier",
    is_active: true,
  });
  const incoming = await postJson(api, "/documents", managerToken, {
    document_type: "incoming",
    document_date: "2026-07-24",
    partner_id: supplier.id,
    warehouse_id: warehouse.id,
  });
  await postJson(api, `/documents/${incoming.id}/lines`, managerToken, {
    product_id: product.id,
    quantity: "1",
    price: "400.00",
  });
  await postJson(api, `/documents/${incoming.id}/post`, managerToken, {});

  const headers = { Authorization: `Bearer ${cashierToken}` };
  await postJson(api, "/cash/operations", cashierToken, {
    operation_date: "2026-07-24",
    operation_type: "cash_in",
    amount: "1000.00",
    note: "M07 supplier payment funding",
  });
  const initialCash = Number((await (await api.get("cash/balance", { headers })).json()).balance);
  await loginAsCashier(page);

  const partialPaymentId = await createAndPostPaymentThroughUi(
    page, api, cashierToken, "supplier_payment", supplier.id, incoming.id, "100.00"
  );
  expect((await (await api.get(`partners/${supplier.id}/balance`, { headers })).json()).balance).toBe("-300.00");

  const fullPaymentId = await createAndPostPaymentThroughUi(
    page, api, cashierToken, "supplier_payment", supplier.id, incoming.id, "300.00"
  );
  expect((await (await api.get(`partners/${supplier.id}/balance`, { headers })).json()).balance).toBe("0.00");

  const overpaymentId = await createAndPostPaymentThroughUi(
    page, api, cashierToken, "supplier_payment", supplier.id, incoming.id, "50.00"
  );
  const [balanceResponse, cashResponse, statementResponse, cashBookResponse] = await Promise.all([
    api.get(`partners/${supplier.id}/balance`, { headers }),
    api.get("cash/balance", { headers }),
    api.get(`partners/${supplier.id}/statement`, { headers }),
    api.get("cash/book", { headers }),
  ]);
  const balance = await balanceResponse.json();
  const cash = await cashResponse.json();
  const statement = await statementResponse.json();
  const cashBook = await cashBookResponse.json();
  const paymentIds = [partialPaymentId, fullPaymentId, overpaymentId];

  expect(balance.balance).toBe("50.00");
  expect(Number(cash.balance)).toBe(initialCash - 450);
  expect(statement.filter((row: { source_type: string; source_id: number }) => (
    row.source_type === "payment" && paymentIds.includes(row.source_id)
  ))).toHaveLength(3);
  expect(cashBook.filter((row: { payment_id: number; operation_type: string }) => (
    paymentIds.includes(row.payment_id) && row.operation_type === "cash_out"
  ))).toHaveLength(3);
  await api.dispose();
});

test("LOG-01: logist sees assigned warehouse and sale price only", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const managerToken = await loginToken(api, "manager@example.com", "manager123");
  const adminToken = await loginToken(api, "admin@example.com", "admin123");
  const warehouse = await postJson(api, "/warehouses", managerToken, {
    code: "E2E-LOGISTICS-WAREHOUSE",
    name: "E2E Logistics Warehouse",
  });
  const product = await postJson(api, "/products", managerToken, {
    sku: "E2E-LOGISTICS-PRODUCT",
    name: "E2E Logistics Product",
    base_price: "150.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", managerToken, {
    code: "E2E-LOGISTICS-SUPPLIER",
    name: "E2E Logistics Supplier",
    partner_type: "supplier",
    is_active: true,
  });
  const incoming = await postJson(api, "/documents", managerToken, {
    document_type: "incoming",
    document_date: "2026-07-24",
    partner_id: supplier.id,
    warehouse_id: warehouse.id,
  });
  await postJson(api, `/documents/${incoming.id}/lines`, managerToken, {
    product_id: product.id,
    quantity: "2",
    price: "80.00",
  });
  await postJson(api, `/documents/${incoming.id}/post`, managerToken, {});
  await postJson(api, "/users", adminToken, {
    email: "logist-e2e@example.com",
    password: "logist123",
    full_name: "E2E Logistics Operator",
    role_names: ["logist"],
    warehouse_ids: [warehouse.id],
  });
  const logistToken = await loginToken(api, "logist-e2e@example.com", "logist123");

  await loginAsLogist(page);
  const navigation = page.getByRole("navigation");
  await expect(navigation.getByRole("link", { name: "Логистика" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Документы" })).toHaveCount(0);
  await expect(navigation.getByRole("link", { name: "Оплаты" })).toHaveCount(0);
  await page.goto("/logistics", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Логистика" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "E2E Logistics Product" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Продажная цена" })).toBeVisible();
  await expect(page.getByText("E2E Logistics Warehouse", { exact: false }).first()).toBeVisible();

  const response = await api.get("logistics/documents", {
    headers: { Authorization: `Bearer ${logistToken}` },
  });
  expect(response.ok()).toBeTruthy();
  const logisticsDocuments = await response.json();
  const logisticsDocument = logisticsDocuments.find((document: { id: number }) => document.id === incoming.id);
  expect(logisticsDocument.lines[0].sale_price).toBe("150.00");
  expect(logisticsDocument.lines[0].sale_total).toBe("300.00");
  expect(logisticsDocument.lines[0]).not.toHaveProperty("price");
  expect(logisticsDocument.lines[0]).not.toHaveProperty("foreign_price");
  expect(logisticsDocument).not.toHaveProperty("currency_code");
  expect(logisticsDocument).not.toHaveProperty("exchange_rate");
  await api.dispose();
});
