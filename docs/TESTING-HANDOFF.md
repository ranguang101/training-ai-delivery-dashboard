# 看板独立测试交接

## R4 质量工作区按需求测试生命周期（已完成独立验收）

- 交接编号：`HO-DT-R4-QUALITY-001`
- 固定组合候选：本交接随同提交；其代码父提交为 `92a74411b17354768d186fe3fe6a78d0b9ecb4c3`。
- 独立验收：固定头 `b189e1b181ea50da8af2bfec739e673ee5c3a455` 已在隔离工作树、独立 8010 实例复验通过；R4 服务端聚焦 65 项、全量 pytest 14 项、质量生命周期 Playwright 3 项均通过。
- 结论：看板 R4 受控页面行为已通过独立测试；不代表 MVP 业务准出、产品验收、试用或发布。
- 变更范围：R4 受控质量需求投影、质量工作区页面、三条需求 Tab、四类聚合卡、详情锚点分区与演示夹具；未改业务功能、业务数据库、迁移、正式 PRD、`roles.product` 或原始测试资产。

### 启动与夹具

在仓库根目录执行：

```powershell
python -m tools.project_dashboard.run --host 127.0.0.1 --port 8010
```

默认只读取本仓 `fixtures/demo-project` 的受控演示夹具。夹具的
`quality_workspace_r4` 段已登记三个固定质量需求、正式 Case、正式执行、
辅助自动化、缺陷和最终报告的演示映射；不会写回原始项目资料。无数据库迁移。

### R4 测试范围

| 需求 | 独立验收重点 |
|---|---|
| QW-REQ-001 | 三个质量需求固定排序、Tab 选择后 URL 保留 `requirement` 与 `line`。 |
| QW-REQ-002—006 | 正式 Case、辅助自动化、缺陷、最终报告四卡统计严格隔离；候选 Case/辅助自动化不影响正式通过；高优先级开放缺陷、阻塞、候选不一致、无有效报告均不得显示可进入产品验收。 |
| QW-REQ-007 | 从四卡进入详情锚点，详情显示 PRD→功能点→Case→执行→缺陷→报告；返回 URL 上下文保持。 |
| QW-REQ-008—009 | 需求与交付线不匹配、缺 R4 映射、接口异常均安全降级并带 `role=alert`；375px 无横向滚动、键盘可访问。 |
| QW-REQ-010 | 原 R3 四工作区与其安全投影仍可访问；R4 不开放原始报告、日志、路径、环境或业务数据。 |

### 开发侧验证与已知限制

- `python -m pytest -q`：14 passed（仅既有 Starlette/httpx 弃用警告）。
- `npx playwright test quality-lifecycle.spec.ts --workers=1 --config playwright.config.ts`：3 passed（使用独立 8024 端口验证）。
- 变更文件 Ruff 与 `git diff --check`：通过。
- 前端负责人当前额度受限；本候选由服务端在既有 R3 视觉体系内完成最小页面接入。测试应以此固定组合独立复验，不将开发自测或演示夹具等同于真实项目准出。

## BUG-DASH-R3-UI-002 复测候选

- 修复候选：当前提交（本次交接随候选一并固化）。
- 复测范围仅为：R3-UI-008、R3-UI-010、R3-UI-016、R3-UI-019。
- 缺陷修复口径：候选未固定、候选不一致、证据不可用、核对日期过期或缺失时，
  “当前交付结论”必须同步降级；不得显示“独立测试通过”、允许进入产品验收、
  允许受控试用，或保留“候选组合已固定”的摘要。
- 默认演示状态不变；本次不代表 MVP 业务准出、产品验收或试用发布。

候选的目的：验证项目交付看板本身的本机只读启动、R3 四工作区投影、故障降级与响应式界面。

## 范围边界

- 默认数据为 `fixtures/demo-project/` 中的无业务数据演示夹具。
- 看板不会启动业务应用、连接业务数据库、加载账号密码、扫描原始报告或访问项目外路径。
- R3 UI 补测状态仅可通过下文列出的测试专用启动参数构造；默认演示数据不会被写入或改动。

## 复现步骤

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm ci
.\.venv\Scripts\python.exe -m pytest -q
npx playwright test --workers=1
.\.venv\Scripts\python.exe -m tools.project_dashboard.run --host 127.0.0.1 --port 8010
```

打开 <http://127.0.0.1:8010/project-status>。

## R3 UI 补测夹具

以下参数仅对当前本机进程的内存投影生效；重启时不带参数即恢复默认演示状态，
无需清理文件或数据库。除 `r3-workspace-503` 外，均在当前工作区页面选择对应交付线后核对页面文案。

| Case | 启动参数 | 选择的交付线 | 预期关键文案 |
|---|---|---|---|
| R3-UI-008 | `--r3-test-fixture pending-candidate` | MVP-B v0.1 人工每日记录闭环 | 候选未固定，当前不可独立测试；状态待核对；不允许进入产品验收/受控试用 |
| R3-UI-010 | `--r3-test-fixture inconsistent-candidate` | MVP-B v0.1 人工每日记录闭环 | 候选不一致，状态待核对；不允许进入产品验收/受控试用 |
| R3-UI-016 | `--r3-test-fixture unavailable-evidence` | MVP-B v0.1 人工每日记录闭环 | 核对证据不可用或日期待补录，当前状态待核对；证据按钮禁用 |
| R3-UI-017 | `--r3-test-fixture empty-line` | R3 UI 空态验证 | 该交付线尚未建立监控事实 |
| R3-UI-018 | `--test-fault r3-workspace-503` | 任一工作区 | 交付信息暂未加载，当前不展示任何通过或准出结论。请刷新重试。 |
| R3-UI-019 | `--r3-test-fixture stale-and-missing-dates` | MVP-B v0.1 / MVP-B 文字学情整理 AI | 部分核对信息已过期，当前状态待复核 / 核对证据不可用或日期待补录，当前状态待核对 |

示例：

```powershell
.\.venv\Scripts\python.exe -m tools.project_dashboard.run --host 127.0.0.1 --port 8010 --r3-test-fixture pending-candidate
```

默认演示回归与清理方式：停止当前管理面板进程后，省略 `--r3-test-fixture` 和
`--test-fault` 重新启动即可。测试夹具不会修改 `fixtures/demo-project/`，不改变正式
交付结论，也不计入正式 Case、缺陷或版本准出统计。

## 独立验收重点

1. 默认启动只监听回环地址；`--host 0.0.0.0` 必须以退出码 2 拒绝。
2. `/api/v1/project-status` 只返回 `project_name` 与 `last_updated`。
3. 交付线和受控证据摘要不包含本机路径、业务数据、账号、密码、原始日志或报告全文。
4. 损坏 `project-status.json` 时页面 200 且以 `role="alert"` 安全降级。
5. 375px 视口无横向滚动；键盘焦点可见。

此交接不代表 MVP 业务准出、产品验收或试用发布。
