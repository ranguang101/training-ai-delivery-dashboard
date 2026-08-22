# 独立项目管理面板

这个工具是开发协作面板，不是业务系统的一部分。它只读取仓库内的
`project-status.json`、`docs/` 和 `reports/test-runs/`；不连接业务数据库，
不执行迁移，也不注册登录、学生或 AI 业务接口。

从仓库根目录启动：

```powershell
.\.venv\Scripts\python.exe -m tools.project_dashboard.run
```

打开：`http://127.0.0.1:8010/project-status`

业务系统未来继续使用 8000 端口；管理面板固定使用本机 8010 端口。若状态资料位于其他项目目录，启动时显式传入 `--project-root`。

启动后先检查安全交付数据接口：

```powershell
Invoke-WebRequest http://127.0.0.1:8010/api/v1/project-status/dashboard -UseBasicParsing
```

预期 HTTP 200 且响应中包含 `data.delivery_lines`。如果返回 404，说明 8010
仍在运行旧管理面板进程；不要处理 8000 业务服务，也不要修改数据库或迁移。由
操作者关闭旧的**管理面板**进程后，再使用上面的命令从当前源码重新启动。

独立测试 404 降级时，使用另一个端口启动受控故障实例：

```powershell
.\.venv\Scripts\python.exe -m tools.project_dashboard.run --port 8012 --test-fault dashboard_404
```

此参数默认关闭；它只影响独立管理面板的安全投影路由，不影响业务服务或数据。
