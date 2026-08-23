import { expect, test } from '@playwright/test';

function r3MockView(cards: Record<string, unknown>, warnings: unknown[] = []) {
  return {
    success: true,
    data: {
      schema_version: 1,
      workspace: { id: 'collaboration', label: '协作总览' },
      line_options: [{ id: 'mvp-b-manual-daily-record', label: 'MVP-B v0.1 人工每日记录闭环' }],
      selected_line: null,
      cards,
      warnings,
    },
  };
}

const mockConclusion = [
  {
    delivery_line_id: 'mvp-b-manual-daily-record',
    name: 'MVP-B v0.1 人工每日记录闭环',
    scope_summary: 'P3-manual 与 P8-min',
    delivery_status: 'integration',
    delivery_status_label: '联调中',
    current_conclusion: '候选组合待核对',
    current_candidate_summary: '候选未固定',
    next_gate_summary: '三角色产品人工验收',
    can_enter_product_acceptance: false,
    can_enter_controlled_trial: false,
    verified_at: '2099-12-31T23:59:59+08:00',
  },
];

function candidateFact(overrides: Record<string, unknown>) {
  return {
    fact_id: 'FACT-MVPB-002',
    delivery_line_id: 'mvp-b-manual-daily-record',
    delivery_line_label: 'MVP-B v0.1 人工每日记录闭环',
    fact_type: 'candidate',
    status: 'verified',
    owner_role: 'development',
    owner_role_label: '服务端技术负责人',
    verified_at: '2099-12-31T23:59:59+08:00',
    summary: 'v0.1 候选组合待核对',
    evidence_refs: [{ type: 'test_run', id: 'RUN-MVP-B-20260813-001000' }],
    workspace_ids: ['collaboration'],
    ...overrides,
  };
}

test('pending candidate shows the fixed pending copy and never claims fixed', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        r3MockView({
          conclusion: { items: mockConclusion },
          progress: { facts: [] },
          gates_and_blockers: {
            facts: [
              candidateFact({
                backend_candidate: '',
                frontend_candidate: '',
                migration_summary: '',
                startup_handoff_ref: '',
                candidate_status: 'pending',
                candidate_status_label: '候选信息待补齐',
                missing_fields: ['backend_candidate', 'frontend_candidate', 'migration_summary', 'startup_handoff_ref'],
                conflict_sources: [],
              }),
            ],
          },
          checked_evidence: { items: [] },
        }),
      ),
    }),
  );
  await page.goto('/project-status/workspaces');
  const candidate = page.locator('[data-r3-candidate="FACT-MVPB-002"]');
  await expect(candidate).toContainText('候选状态');
  await expect(candidate).toContainText('候选信息待补齐');
  await expect(candidate).toContainText('待提供');
  await expect(candidate).toContainText('待补齐：服务端候选、前端候选、迁移说明、启动交接编号');
  await expect(candidate).not.toContainText('候选组合已固定');
});

test('inconsistent candidate shows the fixed conflict copy and lists conflict sources', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        r3MockView({
          conclusion: { items: mockConclusion },
          progress: { facts: [] },
          gates_and_blockers: {
            facts: [
              candidateFact({
                backend_candidate: '9e38e599',
                frontend_candidate: 'ffffffff',
                migration_summary: '不适用',
                startup_handoff_ref: 'HO-PD-013',
                candidate_status: 'inconsistent',
                candidate_status_label: '候选不一致，状态待核对',
                missing_fields: [],
                conflict_sources: ['候选组合与已声明组合不匹配'],
                summary: '候选不一致，状态待核对',
              }),
            ],
          },
          checked_evidence: { items: [] },
        }),
      ),
    }),
  );
  await page.goto('/project-status/workspaces');
  const candidate = page.locator('[data-r3-candidate="FACT-MVPB-002"]');
  await expect(candidate).toContainText('候选不一致，状态待核对');
  await expect(candidate).toContainText('冲突来源：候选组合与已声明组合不匹配');
  await expect(candidate).not.toContainText('候选组合已固定');
  await expect(candidate).not.toContainText('可试用');
});

test('server warnings render as role=alert and never claim a pass', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        r3MockView(
          {
            conclusion: { items: [] },
            progress: { facts: [] },
            gates_and_blockers: { facts: [] },
            checked_evidence: { items: [] },
          },
          [
            { code: 'R3_LINE_NO_FACTS', safe_message: '该交付线尚未建立监控事实' },
            { code: 'R3_CANDIDATE_UNMATCHED', safe_message: '部分候选组合与已声明组合不匹配或存在引用冲突，候选不一致，状态待核对' },
          ],
        ),
      ),
    }),
  );
  await page.goto('/project-status/workspaces');
  const alert = page.locator('.r3-alert');
  await expect(alert).toHaveAttribute('role', 'alert');
  await expect(alert).toContainText('该交付线尚未建立监控事实');
  await expect(alert).toContainText('候选不一致，状态待核对');
});

test('missing fields and missing check dates use the fixed degraded copies', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        r3MockView({
          conclusion: { items: [] },
          progress: {
            facts: [
              {
                fact_id: 'FACT-MISSING-001',
                delivery_line_id: 'mvp-b-manual-daily-record',
                delivery_line_label: 'MVP-B v0.1 人工每日记录闭环',
                fact_type: 'in_progress',
                status: 'pending_check',
                owner_role: 'testing',
                owner_role_label: '测试负责人',
                verified_at: '',
                summary: '',
                evidence_refs: [],
                workspace_ids: ['collaboration'],
              },
            ],
          },
          gates_and_blockers: { facts: [] },
          checked_evidence: { items: [] },
        }),
      ),
    }),
  );
  await page.goto('/project-status/workspaces');
  const progress = page.locator('[data-r3-card="progress"]');
  await expect(progress).toContainText('当前信息待补齐');
  await expect(progress).toContainText('核对日期待补录');
  await expect(progress).toContainText('待核对');
});

test('malicious summaries render as plain text and never execute', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        r3MockView({
          conclusion: { items: [] },
          progress: {
            facts: [
              {
                fact_id: 'FACT-XSS-001',
                delivery_line_id: 'mvp-b-manual-daily-record',
                delivery_line_label: 'MVP-B v0.1 人工每日记录闭环',
                fact_type: 'in_progress',
                status: 'verified',
                owner_role: 'testing',
                owner_role_label: '测试负责人',
                verified_at: '2099-12-31T23:59:59+08:00',
                summary: '<script>window.__xss=1</script><img src=x onerror="window.__xss=2">正常摘要',
                evidence_refs: [],
                workspace_ids: ['collaboration'],
              },
            ],
          },
          gates_and_blockers: { facts: [] },
          checked_evidence: { items: [] },
        }),
      ),
    }),
  );
  await page.goto('/project-status/workspaces');
  const progress = page.locator('[data-r3-card="progress"]');
  await expect(progress).toContainText('<script>window.__xss=1</script>');
  await expect(progress.locator('script')).toHaveCount(0);
  await expect(progress.locator('img')).toHaveCount(0);
  expect(await page.evaluate(() => (window as { __xss?: number }).__xss)).toBeUndefined();
});

test('evidence targets outside the safe href whitelist are never clickable', async ({ page }) => {
  await page.route('**/api/v1/project-status/dashboard/r3/workspaces/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        r3MockView({
          conclusion: { items: mockConclusion },
          progress: { facts: [] },
          gates_and_blockers: {
            facts: [
              {
                fact_id: 'FACT-BADREF-001',
                delivery_line_id: 'mvp-b-manual-daily-record',
                delivery_line_label: 'MVP-B v0.1 人工每日记录闭环',
                fact_type: 'blocked',
                status: 'verified',
                owner_role: 'testing',
                owner_role_label: '测试负责人',
                verified_at: '2099-12-31T23:59:59+08:00',
                summary: '等待证据',
                evidence_refs: [{ type: 'test_run', id: 'BAD ID!' }],
                workspace_ids: ['collaboration'],
              },
            ],
          },
          checked_evidence: {
            items: [
              {
                type: 'test_run',
                id: 'BAD ID!',
                title: '非法编号证据',
                status: 'valid',
                owner_role: 'testing',
                owner_role_label: '测试负责人',
                verified_at: '2099-12-31T23:59:59+08:00',
                safe_summary: '编号不符合安全白名单',
                available: true,
                unavailable_reason: null,
              },
            ],
          },
        }),
      ),
    }),
  );
  await page.goto('/project-status/workspaces');
  const evidenceCard = page.locator('[data-r3-card="evidence"]');
  await expect(evidenceCard).toContainText('证据暂不可查看');
  await expect(evidenceCard.locator('button.r3-evidence-link')).toBeDisabled();
  await evidenceCard.locator('button.r3-evidence-link').click({ force: true });
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('unknown line in the url keeps the honest load failure state', async ({ page }) => {
  await page.goto('/project-status/workspaces?line=no-such-line');
  await expect(page.locator('[role="alert"]')).toContainText(
    '交付信息暂未加载，当前不展示任何通过或准出结论。请刷新重试。',
  );
  await expect(page.locator('.r3-card')).toHaveCount(0);
});
