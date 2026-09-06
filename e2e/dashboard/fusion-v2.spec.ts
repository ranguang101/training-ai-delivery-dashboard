import { expect, test } from '@playwright/test';

test.describe('PRD v2.0 Fusion Dashboard (Plane + MeterSphere)', () => {

  test('v2 page loads with topbar feishu links, 3 plane cards, tree and case table', async ({ page }) => {
    await page.goto('/project-status/v2');

    // 1. Topbar elements
    await expect(page.locator('.brand-title')).toContainText('晚托班 AI 教师提效系统');
    await expect(page.locator('.badge-status')).toContainText('本地只读监控联通中');

    // 3 Feishu Buttons
    const prdBtn = page.locator('#link-feishu-prd');
    await expect(prdBtn).toBeVisible();
    await expect(prdBtn).toHaveAttribute('target', '_blank');
    await expect(prdBtn).toHaveAttribute('href', /feishu\.cn/);

    const casesBtn = page.locator('#link-feishu-cases');
    await expect(casesBtn).toBeVisible();
    await expect(casesBtn).toHaveAttribute('target', '_blank');

    const reportBtn = page.locator('#link-feishu-report');
    await expect(reportBtn).toBeVisible();
    await expect(reportBtn).toHaveAttribute('target', '_blank');

    // 2. Plane Executive Cards
    const moduleCards = page.locator('.module-card');
    await expect(moduleCards).toHaveCount(3);
    await expect(page.locator('.module-card[data-module-id="mvp-a"]')).toHaveClass(/active-module/);

    // 3. Tree and Table
    await expect(page.locator('#tree-list-container')).toBeVisible();
    await expect(page.locator('#pane-title')).toBeVisible();
    await expect(page.locator('#case-tbody tr')).not.toHaveCount(0);
  });

  test('clicking plane module card links to tree node and table filter', async ({ page }) => {
    await page.goto('/project-status/v2');

    // Click MVP-B module card
    await page.locator('.module-card[data-module-id="mvp-b"]').click();
    await expect(page.locator('.module-card[data-module-id="mvp-b"]')).toHaveClass(/active-module/);
    await expect(page.locator('.tree-node[data-node-id="mvp-b"]')).toHaveClass(/active-node/);
    await expect(page.locator('#pane-title')).toContainText('MVP-B');

    // Click back to MVP-A module card
    await page.locator('.module-card[data-module-id="mvp-a"]').click();
    await expect(page.locator('.module-card[data-module-id="mvp-a"]')).toHaveClass(/active-module/);
    await expect(page.locator('.tree-node[data-node-id="mvp-a"]')).toHaveClass(/active-node/);
  });

  test('tree node clicking filters by module', async ({ page }) => {
    await page.goto('/project-status/v2');

    // Click P1 tree node
    await page.locator('.tree-node[data-node-id="P1"]').click();
    await expect(page.locator('.tree-node[data-node-id="P1"]')).toHaveClass(/active-node/);
    await expect(page.locator('#pane-title')).toContainText('P1');

    const p1Pills = page.locator('#case-tbody .pill-gray');
    const p1Count = await p1Pills.count();
    expect(p1Count).toBeGreaterThan(0);
    for (let i = 0; i < p1Count; i++) {
      await expect(p1Pills.nth(i)).toContainText('P1');
    }

    // Click P2 tree node
    await page.locator('.tree-node[data-node-id="P2"]').click();
    await expect(page.locator('.tree-node[data-node-id="P2"]')).toHaveClass(/active-node/);
    await expect(page.locator('#pane-title')).toContainText('P2');

    const p2Pills = page.locator('#case-tbody .pill-gray');
    const p2Count = await p2Pills.count();
    expect(p2Count).toBeGreaterThan(0);
    for (let i = 0; i < p2Count; i++) {
      await expect(p2Pills.nth(i)).toContainText('P2');
    }
  });

  test('drawer slides out on case click and Escape closes it', async ({ page }) => {
    await page.goto('/project-status/v2');

    const drawer = page.locator('#drawer-panel');
    const backdrop = page.locator('#drawer-backdrop');
    await expect(drawer).not.toHaveClass(/open/);

    // Click first row
    await page.locator('#case-tbody tr').first().click();

    await expect(drawer).toHaveClass(/open/);
    await expect(backdrop).toHaveClass(/open/);
    await expect(page.locator('#drawer-title')).not.toBeEmpty();
    await expect(page.locator('#drawer-steps')).not.toBeEmpty();

    // Close via Escape key
    await page.keyboard.press('Escape');
    await expect(drawer).not.toHaveClass(/open/);
    await expect(backdrop).not.toHaveClass(/open/);
  });

  test('full 47-cases PRD dataset: status filtering and dynamic search', async ({ page }) => {
    // Mock standard PRD v2.0 dataset
    const mockCases = [
      {
        id: 'MVP-A-MAIN-001',
        module: 'P1',
        module_name: 'P1 账号权限',
        title: '登录后进入管理首页，检查账号/学生列表与返回',
        automation_kind: 'Playwright 自动化',
        status: 'passed',
        status_label: '通过',
        preconditions: '测试基础环境与租户账号已就绪',
        steps: '1. 访问系统登录页并输入管理员账号\n2. 校验登录跳转\n3. 核对侧边栏列表',
        expected_result: '正常展示管理首页概览',
        actual_result: 'RUN-008 执行通过',
      },
      {
        id: 'MVP-A-MAIN-014',
        module: 'P2',
        module_name: 'P2 学生归属',
        title: '学生归属教师批量转移并在历史中追溯审计日志',
        automation_kind: '人工 / 混合',
        status: 'blocked',
        status_label: '阻塞 (收口中)',
        preconditions: '当前班级存在20名学生',
        steps: '1. 列表多选勾选待调配学生\n2. 点击批量操作弹窗并指定教师',
        expected_result: '批量变更归属并生成审计流',
        actual_result: '当前收口中：批量接口超过20人时偶发耗时告警',
      },
      {
        id: 'MVP-A-CASE-R3-001',
        module: 'P1',
        module_name: 'P1 账号权限',
        title: '交互验收：登录提交',
        automation_kind: 'Playwright 自动化',
        status: 'passed',
        status_label: '通过',
        preconditions: '用户账号就绪',
        steps: '1. 填写账号密码点击登录',
        expected_result: '登录成功跳转',
        actual_result: '通过',
      }
    ];

    await page.route('**/api/v1/project-status/lightweight?page=dashboard_v2', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            project_name: '晚托班 AI 教师提效系统',
            updated_at: '2026-09-06',
            modules: [
              {
                id: 'mvp-a',
                name: 'MVP-A · 管理运营底座',
                sub_title: '包含 P1 账号权限、P2 学生与归属',
                status: 'independent_test',
                status_label: '产品验收通过 · 质量收口中',
                status_pill_class: 'pill-green',
                pass_rate: 66.7,
                cases_total: 3,
                cases_passed: 2,
                cases_blocked: 1,
                active_step: '独立测试 (收口中)',
                blocker_summary: '尚余 1 条 Case 待收口',
                stepper: [
                  { name: '需求冻结 ✓', state: 'done' },
                  { name: '提测 ✓', state: 'done' },
                  { name: '独立测试 (收口中)', state: 'current' },
                  { name: '试用定版', state: 'pending' },
                ]
              },
              {
                id: 'mvp-b',
                name: 'MVP-B · 教师学情工作台',
                sub_title: 'P3 随笔流记录草稿',
                status: 'preparing',
                status_label: '编码前准备',
                status_pill_class: 'pill-amber',
                pass_rate: 0,
                cases_total: 0,
                cases_passed: 0,
                cases_blocked: 0,
                active_step: 'TR-P3契约 (当前)',
                blocker_summary: '冻结 P3 字段级契约',
                stepper: []
              },
              {
                id: 'mvp-b-ai',
                name: 'MVP-B AI · 文字整理增强',
                sub_title: 'P4 关键点提取',
                status: 'planning',
                status_label: '规划中',
                status_pill_class: 'pill-gray',
                pass_rate: 0,
                cases_total: 0,
                cases_passed: 0,
                cases_blocked: 0,
                active_step: 'TR-P4 预研',
                blocker_summary: '整体后置',
                stepper: []
              }
            ],
            feishu_links: {
              prd_url: 'https://vcnzw9ygmgsx.feishu.cn/docx/XHu7dCKI2oYsWZx4oBQcnJwtnxR',
              cases_url: 'https://vcnzw9ygmgsx.feishu.cn/docx/WnTKduhb1oA8UsxGscqc6UgPnug',
              report_url: 'https://vcnzw9ygmgsx.feishu.cn/docx/P5G7dnSxsolcKqxTVhecokFsnof'
            },
            tree: [
              { id: 'all', label: '全部需求', count: 3 },
              {
                id: 'mvp-a', label: 'MVP-A 管理运营底座', count: 3,
                children: [
                  { id: 'P1', label: 'P1 账号与权限管理', count: 2 },
                  { id: 'P2', label: 'P2 学生档案与归属', count: 1 }
                ]
              },
              { id: 'mvp-b', label: 'MVP-B 教师学情工作台', count: 0 }
            ],
            cases: mockCases,
            stats: { total: 3, passed: 2, blocked: 1, pass_rate: 66.7 }
          }
        })
      });
    });

    await page.goto('/project-status/v2');

    // Verify 3 cases loaded
    await expect(page.locator('#case-tbody tr')).toHaveCount(3);
    await expect(page.locator('#stat-total')).toHaveText('3');
    await expect(page.locator('#stat-passed')).toHaveText('2');
    await expect(page.locator('#stat-blocked')).toHaveText('1');

    // Filter by Blocked
    await page.locator('.filter-tab[data-status="blocked"]').click();
    await expect(page.locator('#case-tbody tr')).toHaveCount(1);
    await expect(page.locator('#case-tbody')).toContainText('MVP-A-MAIN-014');
    await expect(page.locator('#case-tbody')).toContainText('阻塞');

    // Filter by Passed
    await page.locator('.filter-tab[data-status="passed"]').click();
    await expect(page.locator('#case-tbody tr')).toHaveCount(2);

    // Search filter
    await page.locator('.filter-tab[data-status="all"]').click();
    const searchInput = page.locator('#tree-search-input');
    await searchInput.fill('批量转移');
    await expect(page.locator('#case-tbody tr')).toHaveCount(1);
    await expect(page.locator('#case-tbody')).toContainText('MVP-A-MAIN-014');

    await searchInput.fill('');
    await expect(page.locator('#case-tbody tr')).toHaveCount(3);
  });
});
