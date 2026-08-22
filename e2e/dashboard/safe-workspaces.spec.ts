import { expect, test } from '@playwright/test';

test('workspaces navigation renders the four safe summaries from the controlled endpoint', async ({ page }) => {
  await page.goto('/project-status/workspaces');

  await expect(page.getByRole('heading', { name: '工作区', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '协作总览', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '服务端工作区', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '前端工作区', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '质量工作区', exact: true })).toBeVisible();
  await expect(page.locator('[data-safe-workspace-overview]')).toContainText('协作总览');
  await expect(page.locator('[data-safe-workspace-overview]')).toContainText('前端工作区');
  await expect(page.locator('[data-safe-workspace-overview]')).toContainText('质量工作区');

  await page.getByRole('link', { name: '查看前端工作区 →' }).click();
  await expect(page).toHaveURL(/\/project-status\/workspaces\/frontend$/);
  await expect(page.locator('#safe-workspace-detail-title')).toHaveText('前端工作区');
  await expect(page.locator('[data-safe-workspace-detail]')).toContainText('负责人：前端开发负责人');
  await expect(page.locator('[data-safe-workspace-detail]')).toContainText('关联交付线');
  await expect(page.locator('[data-safe-workspace-detail]')).toContainText('开放门禁');
});

test('workspace summary clears state and announces a controlled API failure', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/workspaces', async (route) => {
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
  });
  await page.goto('/project-status/workspaces/development');

  const alert = page.getByRole('alert');
  await expect(alert).toContainText('工作区安全摘要未加载');
  await expect(page.locator('.safe-workspace-card')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '重新加载工作区' })).toBeVisible();
});

test('workspace overview safely degrades an empty controlled projection', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/workspaces', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { schema_version: 1, workspaces: [], warnings: ['演示数据待核对。'] },
      }),
    });
  });
  await page.goto('/project-status/workspaces');

  await expect(page.getByRole('alert')).toContainText('演示数据待核对。');
  await expect(page.getByText('当前未显示任何工作区状态。请确认安全数据源可用后刷新页面。')).toBeVisible();
});

test('workspace details reject an unsafe evidence href and retain the safe fallback', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/workspaces', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          schema_version: 1,
          workspaces: [{
            id: 'frontend',
            display_label: '前端工作区',
            owner_role: 'frontend',
            owner_role_label: '前端开发负责人',
            status: 'implementation',
            status_label: '实施中',
            current: '当前工作',
            next: '下一步',
            updated_at: '2026-08-22',
            checked_at: '2026-08-22',
            delivery_line_refs: ['mvp-a-management-foundation'],
            open_blockers: [],
            evidence_links: [{
              label: '不安全证据',
              href: 'file:///D:/private/report.txt',
              safe_summary: '不应成为可点击链接。',
              source_role_label: '前端开发负责人',
              checked_at: '2026-08-22',
            }],
          }],
        },
      }),
    });
  });
  await page.goto('/project-status/workspaces/frontend');

  await expect(page.getByText('证据链接未通过安全白名单校验，已停用。')).toBeVisible();
  await expect(page.getByRole('link', { name: '不安全证据' })).toHaveCount(0);
});

test('narrow workspace view has no horizontal overflow and preserves keyboard focus', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/workspaces/testing');

  await expect(page.locator('#safe-workspace-detail-title')).toHaveText('质量工作区');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('link', { name: '返回工作区' }).focus();
  await expect(page.locator(':focus')).toHaveAttribute('href', '/project-status/workspaces');
});
