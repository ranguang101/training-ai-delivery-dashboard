import { expect, test } from '@playwright/test';

const PAGES: [string, string, string][] = [
  ['/project-status', 'overview', '项目总览'],
  ['/project-status/product', 'product', '产品 / PRD'],
  ['/project-status/frontend', 'frontend', '前端交付'],
  ['/project-status/development', 'development', '服务端交付'],
  ['/project-status/tests', 'testing', '质量 / 测试'],
];

test('five lightweight pages render from the shared project status source', async ({ page }) => {
  for (const [route, pageValue, title] of PAGES) {
    await page.goto(route);
    await expect(page.locator('#dashboard-page-title')).toHaveText(title);
    await expect(page.locator('[data-lightweight-dashboard]')).not.toHaveAttribute(
      'aria-busy',
      'true',
    );
    await expect(page.locator('[data-dashboard-page]')).toHaveAttribute(
      'data-dashboard-page',
      pageValue,
    );
    await expect(page.locator('#lightweight-line-select')).toBeVisible();
  }
});

test('lightweight line context is retained across primary pages', async ({ page }) => {
  await page.goto('/project-status?line=mvp-b-manual-daily-record');
  await expect(page.locator('#lightweight-line-select')).toHaveValue('mvp-b-manual-daily-record');

  const primaryNav = page.getByRole('navigation', { name: '项目一级导航' });
  await primaryNav.getByRole('link', { name: '产品 / PRD' }).click();
  await expect(page).toHaveURL(/\/project-status\/product[?&]line=mvp-b-manual-daily-record/);
  await expect(page.locator('#lightweight-line-select')).toHaveValue('mvp-b-manual-daily-record');
  await expect(page.locator('#product-versions')).toBeVisible();
});

test('evidence level and status display follow the current projection', async ({ page }) => {
  const levels = ['D1', 'D3', 'D5', 'D6'];
  let currentLevel = levels[0];
  await page.route('**/api/v1/project-status/lightweight?*', async (route) => {
    const line = {
      delivery_line_id: 'fixture-line-browser',
      name: 'Synthetic browser line',
      summary: `Synthetic state ${currentLevel}`,
      scope_summary: 'Synthetic browser scope',
      status: { code: 'integration', label: '联调中' },
      evidence_level: { code: currentLevel, label: `Synthetic ${currentLevel}` },
      contract_state: { code: 'frozen', label: '已冻结' },
      candidate_version: { code: 'fixed', label: '候选组合已固定' },
      runtime_gate: { code: 'open', label: '待处理' },
      source_role: { code: 'development', label: '服务端技术负责人' },
      verified_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      blocker_count: 0,
      next_action: 'Synthetic next action',
    };
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          schema_version: 1,
          page: 'overview',
          page_label: '项目总览',
          project: { name: 'Synthetic browser project', updated_at: new Date().toISOString() },
          line_options: [{ id: line.delivery_line_id, label: line.name }],
          selected_line: line,
          data: {
            direction: 'Synthetic direction', summary: 'Synthetic summary',
            progress_percent: null, progress_summary: 'Synthetic baseline',
            lines: [line], decisions: [], roles: {}, recent_updates: [],
          },
          warnings: [],
        },
      }),
    });
  });

  await page.goto('/project-status');
  for (const level of levels) {
    currentLevel = level;
    await page.reload();
    const row = page.locator('.lightweight-line-row').first();
    await expect(row.locator(`[data-status-code="${level}"]`)).toHaveText(`Synthetic ${level}`);
  }
});

test('dashboard DOM remains read-only while navigation and detail controls remain available', async ({ page }) => {
  await page.goto('/project-status');
  await expect(page.locator('form')).toHaveCount(0);
  await expect(page.locator('[method="post"], [method="delete"]')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: '项目一级导航' }).getByRole('link')).toHaveCount(5);
  await expect(page.locator('a[href^="/project-status/delivery-lines/"]').first()).toBeVisible();
});
