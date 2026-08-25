# 项目交付看板代码基线交接

## 目的

本文是独立“项目交付看板”仓库的代码收拢交接依据。看板是本机只读的监管工具，不是业务应用：不得启动业务服务、访问业务数据库，或把业务数据、原始报告、日志、环境信息及本机路径投影到浏览器。

本文只规定运行基线、代码归属和清理边界；不代表 MVP 准出、产品验收、试用发布或业务功能状态。

## 当前交接基线

- 分支：`dashboard-r4-quality-lifecycle-backend`
- 固定提交：`a2a389e19bc3bbf093cf3eb189b74d447783265b`
- 提交链：`39f25ca`（R4 安全投影）→ `92a7441`（R4 页面与生命周期）→ `b189e1b`（测试交接）→ `a2a389e`（独立验收记录）。
- 该链已继承 R3 的安全降级修复 `7335cde`。

后续维护、测试和清理均从该基线新建分支。不得回退到 R2 工作区版本、R3 的早期候选，或旧业务仓的 `/project-status` 实现。

## 保留范围与所有权

### R3：轻量交付监控

保留以下页面壳、前端行为与对应服务端投影：

- `app/templates/_project_nav.html`
- `app/templates/safe_workspace_overview.html`
- `app/templates/safe_workspace_detail.html`
- `app/static/dashboard-shell.js`
- `app/static/project-status-r3.js`
- `app/static/project-status.css`
- `app/services/delivery_monitor.py`
- `e2e/dashboard/r3-lite.spec.ts`
- `tests/integration/test_dashboard_r3_lite_projection.py`
- `tests/integration/test_dashboard_r3_lite_safety.py`

R3 只呈现受控交付线、四工作区、四卡事实和白名单证据详情。浏览器不得自行读取 `project-status.json`、报告或文档正文，也不得自行推断“通过”“可试用”或“发布”。

### R4：质量需求测试生命周期

保留质量需求页面、脚本、投影和回归测试：

- `app/templates/safe_quality_requirements.html`
- `app/static/quality-lifecycle.js`
- `app/services/quality_lifecycle.py`
- `e2e/dashboard/quality-lifecycle.spec.ts`
- `tests/integration/test_quality_lifecycle.py`

`app/routers/project_status.py` 是 R3/R4 共用的受控路由边界，必须整体维护。R4 的三个固定质量需求为 `QR-MVP-A`、`QR-MVP-B-MANUAL`、`QR-MVP-B-TEXT-AI`；正式 Case、辅助自动化、缺陷和最终报告必须保持统计与展示隔离。

### 通用运行、夹具与验证

以下文件是独立运行和可复现演示的必要资产：

- `tools/project_dashboard/run.py`、`tools/project_dashboard/main.py` 及同目录说明；
- `app/services/project_status.py`、`document_catalog.py`、`markdown_safety.py`；
- `fixtures/demo-project/`；
- `tests/integration/_dashboard_fixtures.py`；
- `tests/standalone/test_dashboard_runtime.py`；
- `e2e/dashboard/safe-workspaces.spec.ts`。

## 受控投影边界

服务端负责字段白名单、状态与证据真实性、候选一致性、报告准入、404/错配/空数据响应和演示夹具。前端只负责安全展示、URL 上下文、可访问性、窄屏适配以及错误/空态。

允许的页面只使用受控 API 返回的安全摘要和白名单详情链接。任何未知字段、非法链接、缺失数据、候选不一致、证据失效或核对时间异常，都必须安全降级，且不得保留“独立测试通过”“可进入产品验收”“可试用”之类相矛盾的结论。

## 清理与隔离规则

### 可删除或保持删除

R2 的原始面板表面、原始报告/缺陷/文档详情入口及其旧测试已经移除，后续不得恢复。历史样式仅能在确认未被 R3/R4 选择器引用、R3/R4/安全工作区浏览器回归通过且无兼容承诺后删除。

当前基线未发现可立即删除的额外前端或服务端运行文件。不要做大范围 CSS 重写或仅凭文件名删除共享资产。

### 必须隔离而非删除

- 过程原型和旧 UI 试验仅可留在专用归档分支，不得作为运行或测试基线；
- R2、R3 早期和安全工作区的历史工作树应先核查未推送独有提交和未跟踪文件，再决定回收；
- Git 历史、归档分支和本地工作树是三类不同资产，回收本地工作树不等于删除 Git 历史；
- 旧业务仓的页面、业务接口和测试资产不得复制进独立看板仓库。

## 本地启动与最小验证

在仓库根目录安装依赖后运行：

```powershell
python -m tools.project_dashboard.run --host 127.0.0.1 --port 8010
```

运行器只允许 loopback 地址。建议的最小验证：

```powershell
pytest tests/integration/test_dashboard_r3_lite_projection.py tests/integration/test_dashboard_r3_lite_safety.py tests/integration/test_quality_lifecycle.py -q
npx playwright test e2e/dashboard --workers=1
ruff check app tools tests
git diff --check
```

测试应使用 `fixtures/demo-project/` 受控演示数据；不得依赖旧业务仓运行时、原始项目状态文件或外部报告目录。

## 当前风险与下一步

1. 先确认上述固定提交已推送并作为远端交接头；未推送前不得回收关联工作树。
2. 历史分支较多，任何新任务必须在交接单中重申本基线，避免从早期 R2/R3 候选复现。
3. 前端仍应在下一次变更前对当前基线做一次独立只读代码复核和真实本机服务验证。
4. 后续需求优先复用 R3 受控交付投影与 R4 质量需求模型；多 Tab、插件、历史归档、深度比较与看板编辑均不属于当前范围。
