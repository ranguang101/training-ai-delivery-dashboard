"""PRD v2.0 Plane + MeterSphere 方案四融合架构集成测试与安全回归。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app

FORBIDDEN_TOKENS = [
    "D:\\",
    "C:\\",
    "worktrees",
    "password",
    "token_secret",
]


def test_fusion_dashboard_v2_page_renders_cleanly() -> None:
    app = create_dashboard_app()
    with TestClient(app) as client:
        # 1. 验证 /project-status/v2 页面正常返回并携带高保真融合看板核心 DOM
        resp = client.get("/project-status/v2")
        assert resp.status_code == 200
        assert 'data-dashboard-mode="v2-fusion"' in resp.text
        assert 'id="modules-grid"' in resp.text
        assert 'id="tree-list-container"' in resp.text
        assert 'id="case-tbody"' in resp.text
        assert 'id="drawer-panel"' in resp.text
        assert 'id="toast-container"' in resp.text
        assert 'fusion-dashboard.css' in resp.text
        assert 'fusion-dashboard.js' in resp.text

        # 2. 验证根路径 / 307 重定向到 /project-status/v2
        root_resp = client.get("/", follow_redirects=False)
        assert root_resp.status_code == 307
        assert root_resp.headers["location"] == "/project-status/v2"


def test_fusion_dashboard_v2_api_contract_and_projection() -> None:
    app = create_dashboard_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/project-status/lightweight?page=dashboard_v2")
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is True
        data = json_data["data"]

        # 模块总控卡片
        modules = data["modules"]
        assert len(modules) == 3
        mvp_a = next(m for m in modules if m["id"] == "mvp-a")
        assert mvp_a["name"] == "MVP-A · 管理运营底座"
        assert mvp_a["status"] == "independent_test"
        assert len(mvp_a["stepper"]) == 4

        mvp_b = next(m for m in modules if m["id"] == "mvp-b")
        assert mvp_b["pass_rate"] == 0
        assert mvp_b["cases_total"] in {0, 2}

        # 验证每个模块注入了专属 feishu_links 字段
        for m in modules:
            assert "feishu_links" in m
            assert isinstance(m["feishu_links"], dict)
        assert mvp_a["feishu_links"]["cases_url"] is not None
        assert mvp_a["feishu_links"]["cases_url"].startswith("https://")
        assert mvp_b["feishu_links"]["cases_url"] is None

        # 飞书外链安全检查
        feishu = data["feishu_links"]
        assert "prd_url" in feishu and "cases_url" in feishu and "report_url" in feishu
        for _key, url in feishu.items():
            if url:
                assert url.startswith("https://")
                assert (".feishu.cn/" in url or ".larksuite.com/" in url)

        # 目录树
        tree = data["tree"]
        assert len(tree) >= 3
        all_node = next(t for t in tree if t["id"] == "all")
        assert all_node["label"] == "全部需求"

        # 用例与字段白名单
        cases = data["cases"]
        assert isinstance(cases, list)
        for c in cases:
            assert "id" in c
            assert "module" in c and c["module"] in {"P1", "P2", "P3-record", "P3-review"}
            assert "module_name" in c
            assert "title" in c
            assert "status" in c and c["status"] in {"passed", "blocked"}
            assert "status_label" in c
            assert "preconditions" in c
            assert "steps" in c
            assert "expected_result" in c
            assert "actual_result" in c

            # 安全性检查：无绝对路径注入
            text_dump = str(c)
            for token in FORBIDDEN_TOKENS:
                assert token not in text_dump


def test_fusion_dashboard_v2_empty_state_graceful_fallback(tmp_path: Path) -> None:
    empty_root = tmp_path / "empty_proj"
    empty_root.mkdir()
    # 状态文件不存在或为空时，安全降级不崩溃
    app = create_dashboard_app(project_root=empty_root)
    with TestClient(app) as client:
        resp = client.get("/api/v1/project-status/lightweight?page=dashboard_v2")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["modules"][0]["cases_total"] == 0
        assert data["cases"] == []


def test_fusion_dashboard_v2_with_real_project_data() -> None:
    real_path = Path(r"D:\培训机构AI提效项目")
    if not real_path.exists():
        return
    app = create_dashboard_app(project_root=real_path)
    with TestClient(app) as client:
        resp = client.get("/api/v1/project-status/lightweight?page=dashboard_v2")
        assert resp.status_code == 200
        data = resp.json()["data"]
        stats = data["stats"]
        assert stats["total"] == 47
        assert stats["passed"] == 41
        assert stats["blocked"] == 6
        assert stats["pass_rate"] == 87.2
        assert len(data["cases"]) == 47
