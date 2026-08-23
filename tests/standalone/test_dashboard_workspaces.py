import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from tools.project_dashboard.main import DEFAULT_DASHBOARD_DATA_ROOT, create_dashboard_app


def test_workspace_endpoint_returns_only_declared_safe_fields() -> None:
    with TestClient(create_dashboard_app()) as client:
        response = client.get("/api/v1/project-status/dashboard/workspaces")

    assert response.status_code == 200
    workspaces = response.json()["data"]["workspaces"]
    assert [item["id"] for item in workspaces] == [
        "collaboration",
        "development",
        "frontend",
        "testing",
    ]
    assert set(workspaces[0]) == {
        "id", "display_label", "owner_role", "owner_role_label", "status",
        "status_label", "current", "next", "updated_at", "checked_at",
        "delivery_line_refs", "completed_items", "open_blockers", "evidence_links",
    }
    assert workspaces[0]["completed_items"] == [
        {
            "id": "DEMO-COLLAB-SUMMARY",
            "label": "演示项：跨角色安全摘要范围已核对",
            "checked_at": "2026-08-22",
            "source_role": "project_owner",
            "source_role_label": "项目负责人",
            "evidence_refs": [],
        }
    ]
    assert "D:" not in json.dumps(response.json(), ensure_ascii=False)


def test_undeclared_workspace_data_safely_degrades(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(DEFAULT_DASHBOARD_DATA_ROOT, fixture_root)
    status_path = fixture_root / "project-status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["safe_workspaces"][0]["local_path"] = "D:/sensitive/report.log"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    with TestClient(create_dashboard_app(fixture_root)) as client:
        response = client.get("/api/v1/project-status/dashboard/workspaces")

    assert response.status_code == 200
    assert response.json()["data"]["workspaces"] == []
    assert "D:/sensitive/report.log" not in response.text


def test_completed_items_are_closed_and_keep_a_safe_source(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(DEFAULT_DASHBOARD_DATA_ROOT, fixture_root)
    status_path = fixture_root / "project-status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["safe_workspaces"][2]["completed_items"] = [
        {
            "id": "FRONTEND-SAFE-WORKSPACE-R1",
            "label": "安全工作区页面已完成独立联调",
            "checked_at": "2026-08-22",
            "source_role": "frontend",
            "evidence_refs": [],
        }
    ]
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    with TestClient(create_dashboard_app(fixture_root)) as client:
        response = client.get("/api/v1/project-status/dashboard/workspaces")

    assert response.status_code == 200
    completed = response.json()["data"]["workspaces"][2]["completed_items"]
    assert completed == [
        {
            "id": "FRONTEND-SAFE-WORKSPACE-R1",
            "label": "安全工作区页面已完成独立联调",
            "checked_at": "2026-08-22",
            "source_role": "frontend",
            "source_role_label": "前端开发负责人",
            "evidence_refs": [],
        }
    ]


def test_unsafe_completed_item_safely_degrades_workspace_projection(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(DEFAULT_DASHBOARD_DATA_ROOT, fixture_root)
    status_path = fixture_root / "project-status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["safe_workspaces"][0]["completed_items"] = [
        {
            "id": "COLLAB-001",
            "label": "D:/sensitive/report.log",
            "checked_at": "2026-08-22",
            "source_role": "project_owner",
            "evidence_refs": [],
        }
    ]
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    with TestClient(create_dashboard_app(fixture_root)) as client:
        response = client.get("/api/v1/project-status/dashboard/workspaces")

    assert response.status_code == 200
    assert response.json()["data"]["workspaces"] == []
    assert "D:/sensitive/report.log" not in response.text


def test_duplicate_completed_item_ids_safely_degrade_workspace_projection(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(DEFAULT_DASHBOARD_DATA_ROOT, fixture_root)
    status_path = fixture_root / "project-status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    completed = payload["safe_workspaces"][0]["completed_items"][0]
    payload["safe_workspaces"][0]["completed_items"].append(dict(completed))
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    with TestClient(create_dashboard_app(fixture_root)) as client:
        response = client.get("/api/v1/project-status/dashboard/workspaces")

    assert response.status_code == 200
    assert response.json()["data"]["workspaces"] == []


def test_raw_workspace_route_stays_closed_in_standalone_mode() -> None:
    with TestClient(create_dashboard_app()) as client:
        response = client.get("/api/v1/project-status/development")
    assert response.status_code == 404


def test_safe_workspace_pages_use_new_panel_only_routes() -> None:
    with TestClient(create_dashboard_app()) as client:
        overview = client.get("/project-status/workspaces")
        detail = client.get("/project-status/workspaces/frontend")

    assert overview.status_code == 200
    assert detail.status_code == 200
    assert 'data-r3-workspace="collaboration"' in overview.text
    assert 'data-r3-workspace="frontend"' in detail.text
    assert "data-safe-workspace-overview" not in overview.text
    assert "data-safe-workspace-detail" not in detail.text
    assert "project-status.json" not in overview.text
    assert "project-status.json" not in detail.text
