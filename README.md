# 项目交付看板

这是“晚托班 AI 教师提效系统”的独立、本机只读交付看板。它不启动业务应用、不会访问或迁移业务数据库，也不会对外监听。

## 本地启动

在仓库根目录安装依赖后，可直接启动随仓库提供的安全演示夹具：

```powershell
python -m tools.project_dashboard.run --host 127.0.0.1 --port 8010
```

`--host` 仅允许回环地址；看板接口只提供经过安全投影的 R3 交付事实与受控证据摘要。若需展示另一份项目资料，再显式传入 `--project-root <资料目录>`；该目录仅作为只读数据源，界面代码始终由本仓库提供。

## 验证

```powershell
python -m pytest -q
npx playwright test --workers=1
```

本仓库不包含业务系统源代码、SQLite 数据库、账号密码、原始日志或原始测试报告。
