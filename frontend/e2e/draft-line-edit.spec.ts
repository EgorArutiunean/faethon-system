import { expect, type Page, test } from "@playwright/test";

const products = [
  { id: 10, name: "Исходный товар", sku: "ORIGINAL", base_price: "200.00", latest_purchase_cost: "150.00", is_active: true },
  { id: 11, name: "Заменённый товар", sku: "REPLACEMENT", base_price: "25.50", latest_purchase_cost: "20.00", is_active: true },
];

async function openDraft(page: Page, options: { incoming?: boolean; readOnly?: boolean; rejectUpdate?: boolean; mobile?: boolean } = {}) {
  const incoming = options.incoming ?? false;
  const line = {
    id: 5, document_id: 42, product_id: 10, product_name: products[0].name,
    quantity: "2.000", price: incoming ? "162.00" : "100.00", line_total: incoming ? "324.00" : "200.00",
    foreign_price: incoming ? "10.00" : null, foreign_line_total: incoming ? "20.00" : null,
  };
  const document = {
    id: 42, document_type: incoming ? "incoming" : "outgoing", number: "DRAFT-42", document_date: "2026-10-22",
    status: "draft", partner_id: 1, partner_name: "Контрагент", warehouse_id: 1, warehouse_name: "Склад",
    currency_code: incoming ? "USD" : "RUB_PMR", exchange_rate: incoming ? "16.200000" : "1.000000",
    total_amount: line.line_total, foreign_total_amount: incoming ? "20.00" : "200.00", posting_version: 0, note: null, lines: [line],
  };
  const updates: Array<Record<string, unknown>> = [];
  const lineMutations: string[] = [];
  let posts = 0;
  await page.addInitScript(() => localStorage.setItem("buy-modern-token", "test-manager-token"));
  if (options.mobile) await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { id: 2, email: "manager@example.com", full_name: "Менеджер", role_names: ["manager"], must_change_password: false,
        permissions: ["documents.read", "documents.post", "products.read", "partners.read", "warehouses.read", "stock.read", ...(options.readOnly ? [] : ["documents.update"])],
      } });
    } else if (path === "/api/v1/documents/42") {
      if (request.method() === "PATCH") Object.assign(document, request.postDataJSON());
      await route.fulfill({ json: document });
    } else if (path === "/api/v1/documents/42/post") {
      posts += 1;
      await route.fulfill({ json: { ...document, status: "posted" } });
    } else if (path.startsWith("/api/v1/documents/42/lines")) {
      lineMutations.push(request.method());
      const payload = request.postDataJSON() as Record<string, unknown>;
      updates.push(payload);
      if (options.rejectUpdate) {
        await route.fulfill({ status: 409, json: { detail: "Document is not editable" } });
        return;
      }
      const price = incoming ? Number(payload.foreign_price) * Number(document.exchange_rate) : Number(payload.price);
      Object.assign(line, payload, {
        product_name: products.find((product) => product.id === payload.product_id)?.name,
        price: price.toFixed(2), quantity: Number(payload.quantity).toFixed(3),
        line_total: (price * Number(payload.quantity)).toFixed(2),
        foreign_line_total: incoming ? (Number(payload.foreign_price) * Number(payload.quantity)).toFixed(2) : null,
      });
      document.total_amount = line.line_total;
      document.foreign_total_amount = line.foreign_line_total ?? line.line_total;
      await route.fulfill({ json: line });
    } else if (path.endsWith("/products/options")) {
      const search = (url.searchParams.get("search") ?? "").toLowerCase();
      await route.fulfill({ json: products.filter((product) => `${product.name} ${product.sku}`.toLowerCase().includes(search)) });
    } else if (path.endsWith("/currencies")) {
      await route.fulfill({ json: [
        { id: 1, code: "RUB_PMR", name: "Рубль ПМР", is_base: true, is_active: true },
        { id: 2, code: "USD", name: "Доллар", is_base: false, is_active: true },
      ] });
    } else if (path.endsWith("/warehouses")) {
      await route.fulfill({ json: [{ id: 1, name: "Склад" }] });
    } else if (path.endsWith("/partners/options") || path.endsWith("/partners/1")) {
      const partner = { id: 1, name: "Контрагент", partner_type: "both", is_active: true };
      await route.fulfill({ json: path.endsWith("/partners/1") ? partner : [partner] });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.goto("/documents/42");
  await expect(page.getByTestId("document-line-edit-5")).toBeVisible();
  return { document, updates, lineMutations, posts: () => posts };
}

test("строка черновика меняет товар, количество и цену с сохранением своего ID", async ({ page }) => {
  const state = await openDraft(page, { mobile: true });
  await page.getByTestId("document-line-edit-5").click();
  await expect(page.getByTestId("document-line-editing")).toContainText("Исходный товар");
  await expect(page.getByTestId("document-line-quantity")).toHaveValue("2.000");
  await expect(page.getByTestId("document-line-price")).toHaveValue("100.00");
  await page.getByTestId("document-product").fill("REPLACEMENT");
  await page.getByRole("option", { name: /Заменённый товар/ }).click();
  await page.getByTestId("document-line-quantity").fill("3");
  await page.getByTestId("document-line-price").fill("25.50");
  await page.getByRole("button", { name: "Сохранить строку", exact: true }).click();
  await expect(page.getByTestId("document-line-editing")).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: "Заменённый товар" })).toContainText(/76[,.]50/);
  expect(state.updates).toEqual([{ product_id: 11, quantity: "3", price: "25.50", foreign_price: null }]);
  expect(state.lineMutations).toEqual(["PATCH"]);
  expect(state.document.lines[0].id).toBe(5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("редактирование валютного прихода сохраняет исходную валютную цену и проверку себестоимости", async ({ page }) => {
  const state = await openDraft(page, { incoming: true });
  await page.getByTestId("document-line-edit-5").click();
  await expect(page.getByTestId("document-line-price")).toHaveValue("10.00");
  await expect(page.getByTestId("sale-price-review")).toBeVisible();
  await page.getByTestId("document-line-price").fill("11");
  await page.getByTestId("document-line-quantity").fill("3");
  await page.getByRole("button", { name: "Сохранить строку", exact: true }).click();
  await expect(page.getByTestId("document-line-editing")).toHaveCount(0);
  expect(state.updates).toEqual([{ product_id: 10, quantity: "3", price: "0", foreign_price: "11" }]);
  expect(state.document.total_amount).toBe("534.60");
  expect(state.document.foreign_total_amount).toBe("33.00");
});

test("некорректная или отклонённая строка остаётся в редакторе; отмена не меняет документ", async ({ page }) => {
  const state = await openDraft(page, { rejectUpdate: true });
  await page.getByTestId("document-line-edit-5").click();
  await page.getByTestId("document-line-quantity").fill("0");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByText("Количество должно быть больше нуля").first()).toBeVisible();
  expect(state.updates).toHaveLength(0);
  await page.getByTestId("document-line-quantity").fill("4");
  await page.getByTestId("document-post").click();
  await expect(page.getByText(/Сохраните строку или отмените её редактирование/).first()).toBeVisible();
  expect(state.posts()).toBe(0);
  await page.getByTestId("document-line-add").click();
  await expect(page.locator(".error-panel")).toContainText("Document is not editable");
  await expect(page.getByTestId("document-line-quantity")).toHaveValue("4");
  await expect(page.getByTestId("document-line-editing")).toBeVisible();
  await page.getByTestId("document-line-edit-cancel").click();
  await expect(page.getByTestId("document-line-editing")).toHaveCount(0);
  await expect(page.getByTestId("document-product")).toHaveValue("");
  expect(state.document.lines[0].quantity).toBe("2.000");
  expect(state.lineMutations).toEqual(["PATCH"]);
});

test("чтение документов не даёт права редактировать строку", async ({ page }) => {
  const state = await openDraft(page, { readOnly: true });
  await expect(page.getByTestId("document-line-edit-5")).toBeDisabled();
  await expect(page.getByTestId("document-line-add")).toBeDisabled();
  expect(state.lineMutations).toHaveLength(0);
});
