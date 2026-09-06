import { expect, test } from '@playwright/test';

const FIXED_CARD_TITLES = ['当前交付结论', '进度与责任', '门禁与阻断', '已核对证据'];
const WORKSPACE_ROUTES: [string, string][] = [
  ['/project-status/workspaces', '协作总览'],
  ['/project-status/workspaces/development', '服务端工作区'],
  ['/project-status/workspaces/frontend', '前端工作区'],
  ['/project-status/workspaces/testing', '质量工作区'],
];

test('four workspace pages render exactly four fixed cards in fixed order', async ({ page }) => {
  for (const [route, label] of WORKSPACE_ROUTES) {
    await page.goto(route);
    await expect(page.locator('#r3-workspace-title')).toHaveText(label);
    await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
    await expect(page.locator('.r3-card-title')).toHaveText(FIXED_CARD_TITLES);
    await expect(page.locator('.r3-card')).toHaveCount(4);
  }
});

test('R3 conclusion opens the generic delivery-line detail page', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  await page.getByRole('link', { name: '查看交付线详情' }).first().click();
  await expect(page).toHaveURL(/\/project-status\/delivery-lines\/[A-Za-z0-9_.:-]+/);
  await expect(page.locator('#delivery-detail-title')).toHaveText('交付线通用详情');
  await expect(page.locator('[data-delivery-detail]')).not.toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('[data-delivery-detail]')).toContainText('详情资料待关联');
});

test('source revision change refreshes the current projection', async ({ page }) => {
  const sourcePage = await page.request.get('/project-status/workspaces');
  const sourceHtml = await sourcePage.text();
  const initialRevision = sourceHtml.match(/data-dashboard-revision="([^"]+)"/)?.[1];
  expect(initialRevision).toBeTruthy();

  let syncCalls = 0;
  await page.route('**/api/v1/project-status', async (route) => {
    syncCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          project_name: '交付看板演示项目',
          last_updated: '2026-08-25T10:00:00+08:00',
          revision: syncCalls === 1 ? 'changed-revision' : initialRevision,
        },
      }),
    });
  });

  await page.goto('/project-status/workspaces');
  await expect.poll(() => syncCalls).toBeGreaterThan(1);
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
});

test('five fact types keep their fixed card assignment', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');

  const progress = page.locator('[data-r3-card="progress"]');
  await expect(progress.locator('.r3-fact-type')).toHaveText([
    '已完成',
    '下一步',
    '已完成',
    '已完成',
    '进行中',
    '下一步',
  ]);
  await expect(progress.locator('.r3-type-candidate')).toHaveCount(0);
  await expect(progress.locator('.r3-type-blocked')).toHaveCount(0);

  const gates = page.locator('[data-r3-card="gates"]');
  await expect(gates.locator('.r3-fact-type')).toHaveText(['阻断', '组合候选', '阻断', '阻断']);
  await expect(gates.locator('.r3-type-completed')).toHaveCount(0);

  const conclusion = page.locator('[data-r3-card="conclusion"]');
  await expect(conclusion).toContainText('MVP-A 管理运营底座');
  await expect(conclusion).not.toContainText('FACT-MVPA-001');
  await expect(conclusion).not.toContainText('FACT-MVPB-003');

  const evidence = page.locator('[data-r3-card="evidence"]');
  await expect(evidence).not.toContainText('组合候选');
  await expect(evidence.locator('.r3-status-pill')).toHaveText(['有效', '有效', '有效']);
});

test('fixed candidate group shows five controlled fields and no pass wording', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');

  const candidate = page.locator('[data-r3-candidate="FACT-MVPB-002"]');
  await expect(candidate).toContainText('服务端候选');
  await expect(candidate).toContainText('9e38e599');
  await expect(candidate).toContainText('前端候选');
  await expect(candidate).toContainText('迁移说明');
  await expect(candidate).toContainText('不适用');
  await expect(candidate).toContainText('启动交接编号');
  await expect(candidate).toContainText('HO-PD-013');
  await expect(candidate).toContainText('候选状态');
  await expect(candidate).toContainText('候选组合已固定');
  await expect(candidate).not.toContainText('测试通过');
  await expect(candidate).not.toContainText('可试用');
  await expect(candidate).not.toContainText('已发布');
  await expect(candidate).not.toContainText('产品验收通过');
});

test('line filter is kept on refresh, workspace switch, and overview return focus', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');

  await page.locator('#r3-line-select').selectOption('mvp-b-manual-daily-record');
  await expect(page).toHaveURL(/[?&]line=mvp-b-manual-daily-record/);
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('[data-r3-card="conclusion"]')).toContainText('MVP-B v0.1 人工每日记录闭环');
  await expect(page.locator('[data-r3-card="conclusion"]')).not.toContainText('MVP-A 管理运营底座');
  await expect(page.locator('.r3-fact-row, .r3-candidate-group')).toHaveCount(3);

  await page.reload();
  await expect(page).toHaveURL(/[?&]line=mvp-b-manual-daily-record/);
  await expect(page.locator('#r3-line-select')).toHaveValue('mvp-b-manual-daily-record');
  await expect(page.locator('[data-r3-card="conclusion"]')).toContainText('MVP-B v0.1 人工每日记录闭环');
  await expect(page.locator('[data-r3-card="conclusion"]')).not.toContainText('MVP-A 管理运营底座');

  await page.getByRole('link', { name: '服务端工作区', exact: true }).click();
  await expect(page).toHaveURL(
    /\/project-status\/workspaces\/development[?&]line=mvp-b-manual-daily-record/,
  );
  await expect(page.locator('[data-r3-card="conclusion"]')).toContainText('MVP-B v0.1 人工每日记录闭环');
  await expect(page.locator('[data-r3-card="conclusion"]')).not.toContainText('MVP-A 管理运营底座');

  await page.getByRole('link', { name: '返回项目总览' }).first().click();
  await expect(page).toHaveURL(
    /\/project-status[?&]line=mvp-b-manual-daily-record/,
  );
  await expect(page.locator('#lightweight-line-select')).toHaveValue('mvp-b-manual-daily-record');
});

test('all three delivery lines keep their filter across all four pages', async ({ page }) => {
  const lines = [
    'mvp-a-management-foundation',
    'mvp-b-manual-daily-record',
    'mvp-b-text-ai-enhancement',
  ];
  const pageNames = ['协作总览', '服务端工作区', '前端工作区', '质量工作区'];
  for (const line of lines) {
    await page.goto('/project-status/workspaces');
    await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
    await page.locator('#r3-line-select').selectOption(line);
    await expect(page).toHaveURL(new RegExp(`[?&]line=${line}`));
    for (const name of pageNames) {
      await page.getByRole('link', { name, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`[?&]line=${line}`));
      await expect(page.locator('#r3-line-select')).toHaveValue(line);
      await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
    }
    await page.reload();
    await expect(page).toHaveURL(new RegExp(`[?&]line=${line}`));
    await expect(page.locator('#r3-line-select')).toHaveValue(line);
  }
});

test('switching the delivery line returns the page to the top', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  await page.locator('#r3-line-select').selectOption('mvp-a-management-foundation');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

test('evidence detail shows the controlled projection and returns to the source with line', async ({ page }) => {
  await page.goto('/project-status/workspaces?line=mvp-b-manual-daily-record');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');

  const evidenceButton = page
    .locator('[data-r3-card="evidence"]')
    .getByRole('button', { name: 'MVP-B v0.1 独立测试报告' });
  await evidenceButton.click();

  const dialog = page.getByRole('dialog', { name: '证据详情（受控投影）' });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('稳定编号');
  await expect(dialog).toContainText('RUN-MVP-B-20260813-001000');
  await expect(dialog).toContainText('测试运行');
  await expect(dialog).toContainText('测试负责人');
  await expect(dialog).toContainText('核对日期');
  await expect(dialog).toContainText('受控摘要');
  await expect(dialog).toContainText('关联证据编号');
  await expect(dialog).toContainText('当前交付线');
  await expect(dialog).toContainText('MVP-B v0.1 人工每日记录闭环');

  await dialog.getByRole('button', { name: '返回原工作区' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(evidenceButton).toBeFocused();
  await expect(page).toHaveURL(/[?&]line=mvp-b-manual-daily-record/);
});

test('load failure shows the fixed copy with role=alert and recovery actions', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) => route.abort());
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[role="alert"]')).toContainText(
    '交付信息暂未加载，当前不展示任何通过或准出结论。请刷新重试。',
  );
  await expect(page.getByRole('button', { name: '刷新重试' })).toBeVisible();
  await expect(
    page.locator('.r3-load-failure').getByRole('link', { name: '返回项目总览' }),
  ).toBeVisible();
  await expect(page.locator('.r3-card')).toHaveCount(0);
});

test('empty projection shows the fixed empty state on every card', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          schema_version: 1,
          workspace: { id: 'collaboration', label: '协作总览' },
          line_options: [],
          selected_line: null,
          cards: {
            conclusion: { items: [] },
            progress: { facts: [] },
            gates_and_blockers: { facts: [] },
            checked_evidence: { items: [] },
          },
          warnings: [],
        },
      }),
    }),
  );
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  for (const card of ['conclusion', 'progress', 'gates', 'evidence']) {
    await expect(page.locator(`[data-r3-card="${card}"] .r3-empty`)).toHaveText('当前无此类事实');
  }
  await expect(page.locator('[role="alert"]')).toHaveCount(1);
  await expect(page.locator('.r3-alert')).toHaveAttribute('role', 'alert');
  await expect(page.locator('.r3-alert')).toContainText('当前无此类事实');
});

test('primary navigation keeps the line filter while R3 remains available as a subnav', async ({ page }) => {
  await page.goto('/project-status/workspaces?line=mvp-b-manual-daily-record');
  await expect(page.locator('#r3-line-select')).toHaveValue('mvp-b-manual-daily-record');
  const primaryNav = page.getByRole('navigation', { name: '项目一级导航' });
  await expect(primaryNav.getByRole('link', { name: '项目总览' })).toHaveAttribute(
    'href',
    /line=mvp-b-manual-daily-record/,
  );
  await primaryNav.getByRole('link', { name: '项目总览' }).click();
  await expect(page).toHaveURL(/\/project-status[?&]line=mvp-b-manual-daily-record/);
  await expect(page.locator('#lightweight-line-select')).toHaveValue('mvp-b-manual-daily-record');

  await page.goto('/project-status/workspaces/testing?line=mvp-b-manual-daily-record');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  await page.getByRole('navigation', { name: '项目一级导航' }).getByRole('link', { name: '项目总览' }).click();
  await expect(page).toHaveURL(/\/project-status[?&]line=mvp-b-manual-daily-record/);
  await expect(page.locator('#lightweight-line-select')).toHaveValue('mvp-b-manual-daily-record');
});

test('top navigation follows the latest selected delivery line', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');

  await page.locator('#r3-line-select').selectOption('mvp-a-management-foundation');
  await page.locator('#r3-line-select').selectOption('mvp-b-text-ai-enhancement');
  const primaryNav = page.getByRole('navigation', { name: '项目一级导航' });
  await expect(primaryNav.getByRole('link', { name: '项目总览' })).toHaveAttribute(
    'href',
    /line=mvp-b-text-ai-enhancement/,
  );
  await expect(primaryNav.getByRole('link', { name: '产品 / PRD' })).toHaveAttribute(
    'href',
    /line=mvp-b-text-ai-enhancement/,
  );
});

test('unavailable evidence stays disabled with its server reason', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          schema_version: 1,
          workspace: { id: 'testing', label: '质量工作区' },
          line_options: [{ id: 'mvp-a-management-foundation', label: 'MVP-A 管理运营底座' }],
          selected_line: null,
          cards: {
            conclusion: {
              items: [
                {
                  delivery_line_id: 'mvp-a-management-foundation',
                  name: 'MVP-A 管理运营底座',
                  scope_summary: 'P1/P2',
                  delivery_status: 'independent_test',
                  delivery_status_label: '独立测试中',
                  current_conclusion: '等待项目负责人人工验收',
                  current_candidate_summary: '不涉及组合候选',
                  next_gate_summary: '产品人工验收',
                  can_enter_product_acceptance: false,
                  can_enter_controlled_trial: false,
                  verified_at: '2099-12-31T23:59:59+08:00',
                },
              ],
            },
            progress: { facts: [] },
            gates_and_blockers: {
              facts: [
                {
                  fact_id: 'FACT-STALE-001',
                  delivery_line_id: 'mvp-a-management-foundation',
                  delivery_line_label: 'MVP-A 管理运营底座',
                  fact_type: 'blocked',
                  status: 'stale',
                  owner_role: 'testing',
                  owner_role_label: '测试负责人',
                  verified_at: '2026-08-01T10:00:00+08:00',
                  summary: '等待备份演练证据',
                  evidence_refs: [{ type: 'test_run', id: 'RUN-MVP-A-20260812-001000' }],
                  workspace_ids: ['testing'],
                },
              ],
            },
            checked_evidence: {
              items: [
                {
                  type: 'test_run',
                  id: 'RUN-MVP-A-20260812-001000',
                  title: 'MVP-A 独立测试报告',
                  status: 'stale',
                  owner_role: 'testing',
                  owner_role_label: '测试负责人',
                  verified_at: '2026-08-01T10:00:00+08:00',
                  safe_summary: 'P1/P2 独立测试通过',
                  available: false,
                  unavailable_reason: '待复核',
                },
              ],
            },
          },
          warnings: [],
        },
      }),
    }),
  );
  await page.goto('/project-status/workspaces/testing');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('[data-r3-card="gates"]')).toContainText('待复核');
  const disabled = page.locator('[data-r3-card="evidence"] button.r3-evidence-link');
  await expect(disabled).toBeDisabled();
  await expect(disabled).toHaveText('待复核');
  await disabled.click({ force: true });
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('narrow 375px view has no horizontal overflow and keyboard reaches the line selector', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const [route] of WORKSPACE_ROUTES) {
    await page.goto(route);
    await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  for (let press = 0; press < 14; press += 1) {
    const active = await page.evaluate(() => document.activeElement && document.activeElement.id);
    if (active === 'r3-line-select') break;
    await page.keyboard.press('Tab');
  }
  await expect(page.locator('#r3-line-select')).toBeFocused();
});

test('pages never leak raw paths, external urls, or raw report content', async ({ page }) => {
  await page.goto('/project-status/workspaces');
  await expect(page.locator('[data-r3-workspace]')).not.toHaveAttribute('aria-busy', 'true');
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(/[A-Za-z]:[\\/]/);
  expect(bodyText).not.toMatch(/file:\/\//);
  expect(bodyText).not.toMatch(/reports[\\/]test-runs/);
  const hrefs = await page.locator('a[href]').evaluateAll((links) =>
    links.map((link) => (link as HTMLAnchorElement).getAttribute('href') || ''),
  );
  for (const href of hrefs) {
    expect(href.startsWith('/')).toBe(true);
    expect(href).toMatch(/^\/(project-status|api\/v1\/project-status)/);
  }
});
