# 独立项目管理面板

这个工具是开发协作面板，不是业务系统的一部分。它只读取仓库内的
`project-status.json`、`docs/` 和 `reports/test-runs/`；不连接业务数据库，
不执行迁移，也不注册登录、学生或 AI 业务接口。

从仓库根目录启动：

```powershell
.\.venv\Scripts\python.exe -m tools.project_dashboard.run
```

打开：`http://127.0.0.1:8010/project-status`

默认读取 `DASHBOARD_PROJECT_ROOT` 指定的目录；未设置时优先读取本地正式项目目录
`D:\培训机构AI提效项目`，找不到时才使用仓库内的演示 fixture。若状态资料位于其他项目目录，启动时显式传入 `--project-root`。
业务系统未来继续使用 8000 端口；管理面板固定使用本机 8010 端口。

看板首页提供项目总览、产品 / PRD、前端交付、服务端交付和质量 / 测试五个轻量摘要页。
它们共同读取一个 `project-status.json`，修改该文件即可调整展示内容，不需要改页面代码或数据库。

面板每 10 秒检查 `project-status.json` 的安全 revision；发现源文件变化后会刷新当前投影。服务端只在当前进程内缓存已解析的状态快照，并在文件 revision 变化时失效；文件仍是唯一数据源。涉及文档或报告的受控资料变化时，也应同步更新该状态文件的 `last_updated`，否则面板不会主动刷新。更新项目状态时应先完整写入，再原子替换目标文件，避免面板读取到半写入内容。

启动后先检查 R3 工作区安全投影：

```powershell
Invoke-WebRequest http://127.0.0.1:8010/api/v1/project-status/dashboard/r3/workspaces/collaboration -UseBasicParsing
```

预期 HTTP 200 且响应中包含 `data.cards`。如果返回 404，说明 8010
仍在运行旧管理面板进程；不要处理 8000 业务服务，也不要修改数据库或迁移。由
操作者关闭旧的**管理面板**进程后，再使用上面的命令从当前源码重新启动。

旧的 R2 交付线、原始文档/报告、Case 设计与辅助自动化详情入口均已从独立看板移除；
它们不会通过本仓库重新暴露。

R3 UI 补测可显式传入 `--r3-test-fixture`（候选待补齐、候选不一致、证据不可用、
空交付线、过期/缺失核对时间）或 `--test-fault r3-workspace-503`。这些参数仅改变
当前进程的内存投影；完整场景、预期文案与恢复方式见
[`docs/TESTING-HANDOFF.md`](../../docs/TESTING-HANDOFF.md)。

通用交付线详情是可选的 `delivery_detail` 受控段：已接入的交付线可从 R3
“当前交付结论”进入 `/project-status/delivery-lines/{delivery_line_id}`，并在明确关联时
进入受控证据摘要页。详情段缺失时页面显示“待关联”；所有对象和证据关系由服务端按
`delivery_line_id` 校验，未登记的原始文档、报告、日志、环境、路径和外链不会被页面读取。
