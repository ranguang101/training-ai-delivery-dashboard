import { expect, test } from '@playwright/test';

test('quality requirements use three fixed tabs and four separate lifecycle cards', async ({ page }) => {
  await page.goto('/project-status/tests/requirements');
  await expect(page.locator('[data-quality-requirements]')).not.toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('.qw-tabs a')).toHaveText([
    'MVP-A 管理运营底座',
    'MVP-B 人工每日学情闭环',
    'MVP-B 文字学情 AI 增强',
  ]);
  await expect(page.locator('.qw-card h3')).toHaveText([
    '正式测试 Case',
    '辅助自动化',
    'Jira / 缺陷',
    '最终测试报告',
  ]);
  await expect(page.locator('.qw-card')).toHaveCount(4);
  await expect(page.getByRole('heading', { name: '辅助自动化' }).locator('..')).toContainText(
    '辅助自动化，不等于正式准出',
  );

  await page.getByRole('link', { name: 'MVP-B 人工每日学情闭环', exact: true }).click();
  await expect(page).toHaveURL(/requirement=QR-MVP-B-MANUAL.*line=mvp-b-manual-daily-record/);
  await expect(page.locator('.qw-readiness')).toContainText('MVP-B 人工每日学情闭环');
});

test('detail preserves line context, shows traceability and does not leak raw assets', async ({ page }) => {
  await page.goto('/project-status/tests/requirements?requirement=QR-MVP-B-MANUAL&line=mvp-b-manual-daily-record');
  await expect(page.locator('[data-quality-requirements]')).not.toHaveAttribute('aria-busy', 'true');
  await page.getByRole('link', { name: '查看 Case 列表' }).click();
  await expect(page).toHaveURL(/QR-MVP-B-MANUAL.*line=mvp-b-manual-daily-record.*#cases/);
  await expect(page.locator('#cases')).toContainText('MVP-B-TC-001');
  await expect(page.locator('#automation')).toContainText('辅助自动化，不等于正式准出');
  await expect(page.locator('#reports')).toContainText('RUN-MVP-B-20260813-001000');
  const body = await page.locator('body').innerText();
  expect(body).not.toMatch(/[A-Za-z]:[\\/]/);
  expect(body).not.toContain('independent-test-report.md');
});

test('narrow viewport supports keyboard focus and no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/tests/requirements');
  await expect(page.locator('[data-quality-requirements]')).not.toHaveAttribute('aria-busy', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.locator('a').first()).toBeFocused();
  await page.getByRole('link', { name: 'MVP-B 文字学情 AI 增强', exact: true }).focus();
  await expect(page.getByRole('link', { name: 'MVP-B 文字学情 AI 增强', exact: true })).toBeFocused();
});
