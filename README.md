# 项目交付看板

这是“晚托班 AI 教师提效系统”的独立、本机只读交付看板。它不启动业务应用、不会访问或迁移业务数据库，也不会对外监听。

## 本地启动

在仓库根目录安装依赖后，指定被展示项目的根目录：

```powershell
python -m tools.project_dashboard.run --host 127.0.0.1 --port 8010 --project-root "D:\培训机构AI提效项目"
```

`--host` 仅允许回环地址；看板接口只提供经过安全投影的交付状态、证据摘要和辅助自动化摘要。

## 验证

```powershell
python -m pytest tests/integration/test_dashboard_host_boundary.py `
  tests/integration/test_dashboard_project_root_isolation.py `
  tests/integration/test_dashboard_stage_gating_and_evidence.py `
  tests/integration/test_test_automation_summary.py -q
```

本仓库不包含业务系统源代码、SQLite 数据库、账号密码、原始日志或原始测试报告。
