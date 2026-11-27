import { expect, Page, test } from "@playwright/test";

type Task = {
  id: number;
  document_id: number;
  document_number: string;
  document_date: string;
  document_type: string;
  posting_version: number;
  partner_name: string;
  warehouse_id: number;
  warehouse_name: string;
  task_type: string;
  status: string;
  assigned_to_id: number;
  assigned_to_name: string;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  lines: Array<{ id: number; product_id: number; product_name: string; expected_quantity: string; actual_quantity: string | null; comment: string | null; status: string; sale_price: string; sale_total: string }>;
  events: Array<{ id: number; event_type: string; created_at: string }>;
};

function makeTask(id: number, status = "in_progress"): Task {
  return {
    id, document_id: id + 100, document_number: `IN-${id}`, document_date: "2026-10-22",
    document_type: "incoming", posting_version: 1, partner_name: "Поставщик", warehouse_id: 1,
    warehouse_name: "Основной склад", task_type: "receive", status,
    assigned_to_id: 7, assigned_to_name: "Работник склада", started_at: "2026-10-22T10:00:00Z",
    completed_at: null, created_at: "2026-10-22T09:00:00Z",
    lines: [{ id: id * 10, product_id: id, product_name: `Товар ${id}`, expected_quantity: "5.000", actual_quantity: null, comment: null, status: "pending", sale_price: "100.00", sale_total: "500.00" }],
    events: [{ id, event_type: "started", created_at: "2026-10-22T10:00:00Z" }]
  };
}

async function mockLogistics(page: Page) {
  const tasks = [makeTask(11), makeTask(12), makeTask(13, "needs_review")];
  const state = { failConfirm: false, failReturn: false, hideFromList: false };
  const submitted: { confirms: unknown[]; returns: unknown[] } = { confirms: [], returns: [] };
  await page.addInitScript(() => {
    localStorage.setItem("buy-modern-token", "warehouse-token");
    localStorage.setItem("buy-modern-language", "ru");
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: {
        id: 7, email: "warehouse@example.com", full_name: "Работник склада", role_names: ["logist"],
        permissions: ["logistics.read", "logistics.process", "logistics.review", "documents.read"],
        warehouse_ids: [1], warehouse_names: ["Основной склад"], must_change_password: false
      } });
      return;
    }
    if (path.endsWith("/logistics/tasks")) {
      const status = url.searchParams.get("status");
      await route.fulfill({ json: state.hideFromList ? [] : tasks.filter((task) => !status || task.status === status) });
      return;
    }
    const match = path.match(/\/logistics\/tasks\/(\d+)(?:\/(confirm|return|start))?$/);
    if (match) {
      const task = tasks.find((item) => item.id === Number(match[1]));
      if (!task) {
        await route.fulfill({ status: 404, json: { detail: "Task not found" } });
        return;
      }
      if (match[2] === "confirm") {
        const payload = request.postDataJSON() as { lines: Array<{ line_id: number; actual_quantity: string; comment: string | null }> };
        submitted.confirms.push(payload);
        if (state.failConfirm) {
          await route.fulfill({ status: 409, json: { detail: "Задание не обновлено" } });
          return;
        }
        payload.lines.forEach((input) => {
          const line = task.lines.find((item) => item.id === input.line_id)!;
          line.actual_quantity = input.actual_quantity;
          line.comment = input.comment;
        });
        task.status = task.lines.some((line) => Number(line.actual_quantity) !== Number(line.expected_quantity)) ? "needs_review" : "completed";
      } else if (match[2] === "return") {
        submitted.returns.push(request.postDataJSON());
        if (state.failReturn) {
          await route.fulfill({ status: 409, json: { detail: "Возврат не выполнен" } });
          return;
        }
        task.status = "pending";
      } else if (match[2] === "start") {
        task.status = "in_progress";
      }
      await route.fulfill({ json: task });
      return;
    }
    await route.fulfill({ json: [] });
  });
  return { tasks, state, submitted };
}

async function waitForDraft(page: Page, text: string) {
  await expect.poll(() => page.evaluate((needle) => Object.values(localStorage).some((value) => value.includes(needle)), text)).toBe(true);
}

test("mobile warehouse drafts survive task switching and reload, then clear after confirmation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { submitted } = await mockLogistics(page);
  await page.goto("/logistics?task=11");
  await page.getByTestId("task-line-actual-110").fill("3");
  await page.locator(".logistics-comment-input").fill("Не хватает двух коробок");
  await waitForDraft(page, "Не хватает двух коробок");
  await page.getByRole("button", { name: /IN-12/ }).click();
  await page.getByTestId("task-line-actual-120").fill("4");
  await page.locator(".logistics-comment-input").fill("Повреждена одна коробка");
  await waitForDraft(page, "Повреждена одна коробка");
  await page.getByRole("button", { name: /IN-11/ }).click();
  await expect(page.getByTestId("task-line-actual-110")).toHaveValue("3");
  await expect(page.locator(".logistics-comment-input")).toHaveValue("Не хватает двух коробок");
  await page.reload();
  await expect(page.getByTestId("task-line-actual-110")).toHaveValue("3");
  await expect(page.locator(".logistics-comment-input")).toHaveValue("Не хватает двух коробок");
  await page.getByTestId("confirm-warehouse-task").click();
  await expect(page.getByTestId("confirm-warehouse-task")).toHaveCount(0);
  expect(submitted.confirms).toEqual([{ lines: [{ line_id: 110, actual_quantity: "3", comment: "Не хватает двух коробок" }] }]);
  await expect.poll(() => page.evaluate(() => Object.values(localStorage).some((value) => value.includes("Не хватает двух коробок")))).toBe(false);
  await page.getByRole("button", { name: /IN-12/ }).click();
  await expect(page.getByTestId("task-line-actual-120")).toHaveValue("4");
});

test("warehouse input survives refresh and a failed confirmation", async ({ page }) => {
  const { state } = await mockLogistics(page);
  state.failConfirm = true;
  await page.goto("/logistics?task=11");
  await page.getByTestId("task-line-actual-110").fill("2");
  await page.locator(".logistics-comment-input").fill("Проверить недостачу");
  await waitForDraft(page, "Проверить недостачу");
  await page.getByRole("button", { name: "Синхронизация", exact: true }).click();
  await expect(page.getByTestId("task-line-actual-110")).toHaveValue("2");
  await page.getByTestId("confirm-warehouse-task").click();
  await expect(page.locator(".logistics-error")).toContainText("Задание не обновлено");
  await page.reload();
  await expect(page.getByTestId("task-line-actual-110")).toHaveValue("2");
  await expect(page.locator(".logistics-comment-input")).toHaveValue("Проверить недостачу");
});

test("warehouse recovery rejects input from a different document version", async ({ page }) => {
  const { tasks } = await mockLogistics(page);
  await page.goto("/logistics?task=11");
  await page.getByTestId("task-line-actual-110").fill("1");
  await page.locator(".logistics-comment-input").fill("Старая версия задания");
  await waitForDraft(page, "Старая версия задания");
  tasks[0].posting_version = 2;
  tasks[0].lines[0].expected_quantity = "8.000";
  await page.reload();
  await expect(page.getByTestId("task-line-actual-110")).toHaveValue("8.000");
  await expect(page.locator(".logistics-comment-input")).toHaveValue("");
  await expect(page.locator(".draft-recovery-notice")).toContainText(/измен|верси/i);
});

test("review note is recovered and cleared only after a successful return", async ({ page }) => {
  const { state, submitted } = await mockLogistics(page);
  state.failReturn = true;
  await page.goto("/logistics?task=13");
  await page.getByTestId("warehouse-task-review-note").fill("Пересчитать коробки у ворот");
  await waitForDraft(page, "Пересчитать коробки у ворот");
  await page.reload();
  await expect(page.getByTestId("warehouse-task-review-note")).toHaveValue("Пересчитать коробки у ворот");
  await page.getByRole("button", { name: /Вернуть на уточнение/ }).click();
  await expect(page.locator(".logistics-error")).toContainText("Возврат не выполнен");
  await expect(page.getByTestId("warehouse-task-review-note")).toHaveValue("Пересчитать коробки у ворот");
  state.failReturn = false;
  await page.getByRole("button", { name: /Вернуть на уточнение/ }).click();
  await expect(page.getByTestId("warehouse-task-review-note")).toHaveCount(0);
  expect(submitted.returns).toEqual([{ note: "Пересчитать коробки у ворот" }, { note: "Пересчитать коробки у ворот" }]);
  await expect.poll(() => page.evaluate(() => Object.values(localStorage).some((value) => value.includes("Пересчитать коробки у ворот")))).toBe(false);
});

test("an exact linked warehouse task opens outside the queue, and missing links never select another task", async ({ page }) => {
  const { state } = await mockLogistics(page);
  state.hideFromList = true;
  await page.goto("/logistics?task=12");
  await expect(page.getByRole("heading", { name: "IN-12", exact: true })).toBeVisible();
  await page.goto("/logistics?task=999");
  await expect(page.locator(".logistics-error")).toBeVisible();
  await expect(page.locator(".logistics-detail-header")).toHaveCount(0);
  state.hideFromList = false;
  await page.goto("/logistics?task=invalid");
  await expect(page.locator(".logistics-task-row")).toHaveCount(3);
  await expect(page.locator(".logistics-error")).toBeVisible();
  await expect(page.locator(".logistics-detail-header")).toHaveCount(0);
});
