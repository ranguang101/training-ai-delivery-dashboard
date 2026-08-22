import { expect, test } from '@playwright/test';

test('standalone dashboard starts with the bundled safe demo', async ({ page }) => {
  await page.goto('/project-status');
  await expect(page.getByRole('heading', { name: '交付看板演示项目' })).toBeVisible();
  await expect(page.locator('[data-delivery-lines-content]')).toContainText('MVP-A · 管理运营底座');
  await expect(page.locator('[data-delivery-lines-content]')).toContainText('等待独立验收');
  await expect(page.getByText('正式 Case 通过')).toHaveCount(0);
});

test('automation summary stays separate from formal test outcomes', async ({ page }) => {
  await page.goto('/project-status/tests/automation');
  await expect(page.getByRole('link', { name: '查看辅助运行 →' })).toHaveAttribute(
    'href',
    '/project-status/tests/automation/runs/AUX-P1-TC-021-20260815-001',
  );
  await expect(page.getByText('P1-TC-021', { exact: true })).toBeVisible();
  await expect(page.getByText('待测试负责人补录')).toBeVisible();
  await expect(page.getByText('辅助 UI 自动化不等于正式测试或版本准出。')).toBeVisible();
});

test('narrow view has no horizontal overflow and keeps keyboard focus visible', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus')).toBeVisible();
});
