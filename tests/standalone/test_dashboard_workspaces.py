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
        "delivery_line_refs", "open_blockers", "evidence_links",
    }
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
    assert "data-safe-workspace-overview" in overview.text
    assert 'data-safe-workspace-detail="frontend"' in detail.text
    assert "project-status.json" not in overview.text
    assert "project-status.json" not in detail.text
