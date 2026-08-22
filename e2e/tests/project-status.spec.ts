import { expect, test } from '@playwright/test';
import { spawn } from 'child_process';
import net from 'net';
import path from 'path';

const projectRoot = path.resolve(__dirname, '..', '..');
const panelPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe');

async function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const address = server.address() as net.AddressInfo;
      server.close(() => resolve(address.port));
    });
    server.on('error', reject);
  });
}

async function waitForServer(url: string, timeoutMs = 20000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // server not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`server not ready: ${url}`);
}

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
  // 交付线导航链接已随原型页面下线；按当前看板口径验证版本卡与键盘焦点。
  await expect(page.getByText('当前交付版本', { exact: true })).toBeVisible();
  const expand = page.getByRole('button', { name: '展开' }).first();
  await expand.focus();
  await expect(expand).toBeFocused();
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

test('交付线证据链接仅渲染通过安全白名单的地址', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    const line = payload.data.delivery_lines.find(
      (item: { id: string }) => item.id === 'mvp-b-daily-record-closure',
    );
    line.evidence_links[0].href = 'file:///D:/private/raw-report.md';
    line.evidence_links[1].href = 'https://external.example/evidence.md';
    await route.fulfill({ response, json: payload });
  });
  await page.goto('/project-status');

  const recordModule = page.locator('#delivery-line-mvp-b-daily-record-closure');
  await recordModule.getByText('查看门槛、证据与后置范围').click();
  await expect(page.getByText('证据链接不可用：未通过安全白名单校验。')).toHaveCount(2);
  await expect(page.locator('a[href="file:///D:/private/raw-report.md"]')).toHaveCount(0);
  await expect(page.locator('a[href="https://external.example/evidence.md"]')).toHaveCount(0);

  const managementModule = page.locator('#delivery-line-mvp-a-management-foundation');
  await managementModule.getByText('查看门槛、证据与后置范围').click();
  const safeEvidenceLinks = managementModule.locator('a[data-delivery-evidence]');
  await expect(safeEvidenceLinks.first()).toHaveAttribute(
    'href',
    /\/api\/v1\/project-status\/dashboard\/delivery-lines\/mvp-a-management-foundation\/evidence\//,
  );
});

test('窄屏独立看板保留同步失败反馈且不横向溢出', async ({ page }) => {
  test.setTimeout(90000);
  const port = await freePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  const panel = spawn(
    panelPython,
    ['-m', 'tools.project_dashboard.run', '--host', '127.0.0.1', '--port', String(port)],
    { cwd: projectRoot, stdio: 'ignore' },
  );
  try {
    await waitForServer(`${baseUrl}/project-status`);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.route('**/api/v1/project-status', (route) => route.fulfill({ status: 503 }));
    await page.goto(`${baseUrl}/project-status`);

    const syncStatus = page.locator('#sync-status');
    await expect(syncStatus).toHaveText('暂时无法同步', { timeout: 20000 });
    const syncPanel = page.locator('.sync-panel');
    await expect(syncPanel).toBeVisible();
    await expect(syncPanel.locator('.sync-dot')).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      bodyWidth: document.body.scrollWidth,
      viewportWidth: window.innerWidth,
    }));
    expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
  } finally {
    panel.kill();
  }
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

  const errorPanel = page.locator('.delivery-load-error');
  const alert = errorPanel.getByRole('alert');
  await expect(alert).toContainText('交付线证据未加载：当前未显示任何交付状态。请确认安全看板服务可用后重试。');
  await expect(errorPanel.getByRole('button', { name: '重新加载交付线' })).toBeVisible();
  await expect(page.locator('.delivery-line-card')).toHaveCount(0);

  isUnavailable = false;
  await errorPanel.getByRole('button', { name: '重新加载交付线' }).click();
  await expect(page.locator('.delivery-line-card')).toHaveCount(2);
});

test('文档详情以可访问的阅读清单呈现内部链接', async ({ page }) => {
  await page.goto('/project-status/documents/334b5eacb1e9');

  const content = page.locator('.markdown-body');
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

  await expect(page.locator('.markdown-body > ol > li').first()).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});
test('质量工作区可以查看 P0 Case 和缺陷', async ({ page }) => {
  await page.goto('/project-status');

  await page.getByLabel('项目一级导航').getByRole('link', { name: '质量工作区', exact: true }).click();
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
  await expect(page.getByText('候选数据不进入正式 Case 统计，也不表示已执行、已通过或已准出。')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('当前未显示任何候选 Case 数据');
  await expect(page.getByLabel('项目一级导航').getByRole('link', { name: '质量工作区', exact: true })).toHaveClass(/is-active/);

  const dimensions = await page.evaluate(() => ({
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(dimensions.bodyWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
});
