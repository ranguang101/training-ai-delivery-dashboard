# 看板独立测试交接

候选的目的：验证项目交付看板本身的本机只读启动、安全投影、故障降级与响应式界面。

## 范围边界

- 默认数据为 `fixtures/demo-project/` 中的无业务数据演示夹具。
- 看板不会启动业务应用、连接业务数据库、加载账号密码、扫描原始报告或访问项目外路径。
- 辅助 UI 自动化仅展示“待测试负责人复核”的受控摘要；不改变正式 Case、缺陷或版本准出统计。

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

## 独立验收重点

1. 默认启动只监听回环地址；`--host 0.0.0.0` 必须以退出码 2 拒绝。
2. `/api/v1/project-status` 只返回 `project_name` 与 `last_updated`。
3. 交付线和辅助自动化摘要不包含本机路径、业务数据、账号、密码、原始日志或报告全文。
4. 损坏 `project-status.json` 时页面 200 且以 `role="alert"` 安全降级。
5. 375px 视口无横向滚动；键盘焦点可见。

此交接不代表 MVP 业务准出、产品验收或试用发布。
