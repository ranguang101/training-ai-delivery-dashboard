import { expect, test } from '@playwright/test';

test('项目总览可以进入 P0 阶段详情', async ({ page }) => {
  await page.goto('/project-status');

  await page.getByRole('link', { name: '查看 P0 项目基线 详情' }).click();

  await expect(page.getByRole('heading', { name: '项目基线' })).toBeVisible();
  await expect(page.getByText('P0-MIG-001', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '开发进度' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '你的测试进度' })).toBeVisible();
});

test('项目总览可以进入服务端工作区', async ({ page }) => {
  await page.goto('/project-status');

  await page.getByRole('link', { name: '工作区', exact: true }).click();
  await page.getByRole('link', { name: '服务端工作区', exact: true }).click();

  await expect(
    page.getByRole('heading', { name: '服务端技术方案、代码验收与前端联调' }),
  ).toBeVisible();
  await expect(page.getByText('当前窗口的长期工作边界')).toBeVisible();
});

test('工作区可以进入前端工作区', async ({ page }) => {
  await page.goto('/project-status');

  await page.getByRole('link', { name: '工作区', exact: true }).click();
  await page.getByRole('link', { name: '前端工作区', exact: true }).click();

  await expect(
    page.getByRole('heading', { name: '前端页面实施、浏览器验证与联调' }),
  ).toBeVisible();
  await expect(page.getByText('测试证据与恢复')).toBeVisible();
  const deliveryLink = page.locator('[data-delivery-nav-link]');
  await expect(deliveryLink).toBeVisible();
  await deliveryLink.focus();
  await expect(deliveryLink).toBeFocused();
  await deliveryLink.click();
  await expect(page).toHaveURL(/\/project-status#delivery-line-mvp-a-management-foundation/);
});

test('前端工作区在窄屏仍保留可用导航与内容', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/frontend');

  await expect(page.getByRole('link', { name: '前端工作区', exact: true })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: '前端页面实施、浏览器验证与联调' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: '测试证据与恢复' })).toBeVisible();
});

test('前端工作区可切换管理员、教师与通用组件原型', async ({ page }) => {
  await page.goto('/project-status/frontend');

  await expect(page.getByRole('heading', { name: '面板组件原型' })).toBeVisible();
  await expect(page.getByText('教师归属审批', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '教师面板' }).click();
  await expect(page.getByText('今日学习记录任务　3 / 8', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '通用组件' }).click();
  await expect(page.getByRole('button', { name: '主要操作' })).toBeVisible();
  await page.getByRole('button', { name: '主要操作' }).click();
  await expect(page.getByText('演示：主要操作已执行并显示成功反馈。')).toBeVisible();
});

test('窄屏前端工作区的教师组件原型不横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/frontend');
  await page.getByRole('tab', { name: '教师面板' }).click();
  await expect(page.getByText('今日学习记录任务　3 / 8', { exact: true })).toBeVisible();
  const dimensions = await page.evaluate(() => ({ bodyWidth: document.body.scrollWidth, viewportWidth: window.innerWidth }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});

test('版本卡从同一来源展示并支持展开和复制', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/project-status/frontend');

  await expect(page.getByText('0.1.0-p1', { exact: true })).toBeVisible();
  await expect(page.locator('[data-release-commit-short]').first()).toHaveText('1c950ced792a');
  await expect(page.locator('[data-release-commit-full]').first()).toBeHidden();
  await page.getByRole('button', { name: '展开' }).first().click();
  await expect(page.locator('[data-release-commit-full]').first()).toHaveText('1c950ced792a3d8d2cb95fc6993fd8b05d3fb931');
  await page.getByRole('button', { name: '复制' }).first().click();
  await expect(page.getByRole('button', { name: '已复制' }).first()).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('1c950ced792a3d8d2cb95fc6993fd8b05d3fb931');

  for (const target of ['/project-status/development', '/project-status/frontend', '/project-status/tests']) {
    await page.goto(target);
    await expect(page.getByText('0.1.0-p1', { exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: '查看 HO-DT-003 提测交接 →' })).toHaveAttribute(
      'href',
      '/project-status/collaboration#handoff-HO-DT-003',
    );
  }

  await page.goto('/project-status/collaboration#handoff-HO-DT-003');
  await expect(page.locator('#handoff-HO-DT-003')).toContainText('提测版本 0.1.0-p1');
  await expect(page.locator('#handoff-HO-DT-003')).toContainText('1c950ced792a');

  await page.goto('/project-status/test-runs/RUN-P1-20260809-201500');
  await expect(page.getByText('运行版本：', { exact: false })).toBeVisible();
  await expect(page.getByText('0.1.0-p1', { exact: true })).toBeVisible();
});

test('项目总览从安全投影展示两个 MVP 模块而不误报可试用', async ({ page }) => {
  await page.goto('/project-status');

  await expect(page.getByRole('heading', { name: 'MVP 交付模块', exact: true })).toBeVisible();
  const managementModule = page.locator('#delivery-line-mvp-a-management-foundation');
  const recordModule = page.locator('#delivery-line-mvp-b-daily-record-closure');
  await expect(page.locator('.delivery-module-card')).toHaveCount(2);
  await expect(managementModule).toContainText('MVP-A · 管理运营底座');
  await expect(managementModule).toContainText('MVP-A 可复现基线与最小人工确认');
  await expect(recordModule).toContainText('MVP-B · 教师每日学情闭环');
  await expect(recordModule).toContainText('P3 人工闭环契约冻结');
  await expect(recordModule.getByText('查看门槛、证据与后置范围')).toBeVisible();
  await recordModule.getByText('查看门槛、证据与后置范围').click();
  await expect(recordModule.getByRole('link', { name: '人工每日记录试用闭环 v0.1 产品方案' })).toHaveAttribute(
    'href',
    /\/api\/v1\/project-status\/dashboard\/delivery-lines\/mvp-b-daily-record-closure\/evidence\//,
  );
  await expect(page.getByRole('heading', { name: 'P0—P8 研发能力追踪' })).toBeVisible();
  await expect(page.getByText('可试用', { exact: true })).toHaveCount(0);
});

test('窄屏版本卡默认短提交且不横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/frontend');

  await expect(page.locator('[data-release-commit-short]')).toHaveText('1c950ced792a');
  await expect(page.locator('[data-release-commit-full]')).toBeHidden();
  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});

test('窄屏产品交付线可读且不横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status');

  await expect(page.getByRole('heading', { name: 'MVP 交付模块', exact: true })).toBeVisible();
  await expect(page.locator('.delivery-module-card')).toHaveCount(2);
  await expect(page.getByText('MVP-A · 管理运营底座', { exact: true })).toBeVisible();
  await expect(page.getByText('MVP-B · 教师每日学情闭环', { exact: true })).toBeVisible();
  await expect(page.getByText('not_frozen', { exact: true })).toHaveCount(0);
  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});

test('安全投影不可用时交付线显示明确降级错误', async ({ page }) => {
  let isUnavailable = true;
  await page.route('**/api/v1/project-status/dashboard', async (route) => {
    if (isUnavailable) {
      await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' });
      return;
    }
    await route.continue();
  });
  await page.goto('/project-status');

  const alert = page.getByRole('alert');
  await expect(alert).toContainText('交付线证据未加载：当前未显示任何交付状态。请确认安全看板服务可用后重试。');
  await expect(alert.getByRole('button', { name: '重新加载交付线' })).toBeVisible();
  await expect(page.locator('.delivery-line-card')).toHaveCount(0);

  isUnavailable = false;
  await alert.getByRole('button', { name: '重新加载交付线' }).click();
  await expect(page.locator('.delivery-line-card')).toHaveCount(2);
});

test('文档详情以可访问的阅读清单呈现内部链接', async ({ page }) => {
  await page.goto('/project-status/documents/334b5eacb1e9');

  const content = page.locator('.document-content');
  const readingList = content.locator('> ol').first();
  const resourceList = content.locator('> ul').first();
  await expect(content).toBeVisible();
  await expect(page.getByRole('heading', { name: '当前建议优先阅读' })).toBeVisible();
  await expect(readingList.locator('> li')).toHaveCount(18);
  await expect(resourceList.locator('> li')).toHaveCount(7);

  const firstLink = readingList.locator('> li > a').first();
  await expect(firstLink).toHaveAttribute('href', /\/project-status\/documents\//);
  await firstLink.focus();
  await expect(firstLink).toBeFocused();
  await firstLink.click();
  await expect(page).toHaveURL(/\/project-status\/documents\/[a-f0-9]+/);
});

test('窄屏文档详情不横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/documents/334b5eacb1e9');

  await expect(page.locator('.document-content > ol > li').first()).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});
test('质量工作区可以查看 P0 Case 和缺陷', async ({ page }) => {
  await page.goto('/project-status');

  await page.getByRole('link', { name: '工作区', exact: true }).click();
  await page.getByRole('link', { name: '质量工作区', exact: true }).click();
  await expect(page.getByRole('heading', { name: '质量工作区：P0、P1测试体系已经进入看板' })).toBeVisible();

  await page.locator('a[href="/project-status/stages/P0/tests"]').click();
  await expect(page.getByRole('heading', { name: '项目基线测试方案' })).toBeVisible();
  await expect(page.getByText('P0-TC-001', { exact: true })).toBeVisible();
  await expect(page.getByText('BUG-P0-001', { exact: true })).toBeVisible();
});

test('质量工作区提供只读 Case 设计入口并在缺少资产时安全降级', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/project-status/tests');

  const entry = page.getByRole('link', { name: '进入只读设计任务 →' });
  await expect(entry).toBeVisible();
  await entry.focus();
  await expect(entry).toBeFocused();
  await entry.click();

  await expect(page).toHaveURL('/project-status/tests/case-design');
  await expect(page.getByRole('heading', { name: '候选 Case 设计任务' })).toBeVisible();
  await expect(page.getByText('候选 Case 不计入正式 Case 统计，也不表示已执行、已通过或已准出。')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('当前未显示任何候选 Case 数据');
  await expect(page.getByRole('link', { name: '质量工作区', exact: true })).toHaveClass(/is-active/);

  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});
