import { expect, test } from '@playwright/test';

test('质量工作区的辅助自动化入口与正式 Case 统计隔离', async ({ page }) => {
  await page.goto('/project-status/tests');

  const entry = page.getByTestId('test-automation-entry');
  await expect(entry).toBeVisible();
  await expect(page.getByText('不计入正式 Case、执行、通过、缺陷或版本准出统计')).toBeVisible();
  await entry.focus();
  await expect(entry).toBeFocused();
  await entry.click();
  await expect(page).toHaveURL('/project-status/tests/automation');
  await expect(page.getByRole('heading', { name: '辅助 UI 自动化：先辅助复核，不替代正式结论' })).toBeVisible();
  await expect(page.getByText('P1-TC-021', { exact: true })).toBeVisible();
  await expect(page.getByText('辅助执行完成 · 待测试复核', { exact: true })).toBeVisible();

  const run = page.getByTestId('test-automation-run-link');
  await run.focus();
  await expect(run).toBeFocused();
  await run.click();
  await expect(page).toHaveURL('/project-status/tests/automation/runs/AUX-P1-TC-021-20260815-001');
  await expect(page.getByText('本次为辅助自动化执行，不更新正式 Case 状态')).toBeVisible();
  await expect(page.getByText('待测试负责人补录', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '安全证据入口' })).toBeVisible();
});

test('受控接口失败时清空辅助状态并提供可访问恢复说明', async ({ page }) => {
  await page.route('**/api/v1/project-status/test-automation', (route) => route.fulfill({ status: 503 }));
  await page.goto('/project-status/tests/automation');

  await expect(page.getByRole('alert')).toContainText('当前未显示任何辅助自动化状态');
  await expect(page.getByText('P1-TC-021', { exact: true })).not.toBeVisible();
});

test('辅助自动化详情在 375px 保持可读', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/tests/automation/runs/AUX-P1-TC-021-20260815-001');

  await expect(page.getByRole('heading', { name: '辅助运行详情' })).toBeVisible();
  await expect(page.getByText('11 项断言', { exact: true })).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});
