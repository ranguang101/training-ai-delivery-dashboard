"""F-02: raw project data must not be a standalone-panel data entry."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app

RAW_DATA_APIS = (
    "/api/v1/project-status/collaboration",
    "/api/v1/project-status/development",
    "/api/v1/project-status/frontend",
    "/api/v1/project-status/tests",
)

RAW_DETAIL_PAGES = (
    "/project-status/collaboration",
    "/project-status/development",
    "/project-status/frontend",
    "/project-status/technical-reviews",
    "/project-status/documents",
    "/project-status/documents/334b5eacb1e9",
    "/project-status/stages/P1",
    "/project-status/stages/P1/tests",
    "/project-status/test-runs/RUN-P1-20260809-201500",
    "/project-status/defects",
    "/project-status/defects/BUG-P0-001",
)


def test_panel_closes_raw_data_apis() -> None:
    with TestClient(create_dashboard_app()) as client:
        for path in RAW_DATA_APIS:
            response = client.get(path)
            assert response.status_code == 404, path
            assert response.json()["detail"] == "PROJECT_STATUS_ROUTE_CLOSED_IN_PANEL"


def test_panel_closes_raw_detail_pages() -> None:
    with TestClient(create_dashboard_app()) as client:
        for path in RAW_DETAIL_PAGES:
            response = client.get(path)
            assert response.status_code == 404, path
            assert response.json()["detail"] == "PROJECT_STATUS_ROUTE_CLOSED_IN_PANEL"


def test_panel_status_api_returns_only_sync_safe_fields() -> None:
    """The polling endpoint must be a safe projection, never raw project data."""
    with TestClient(create_dashboard_app()) as client:
        response = client.get("/api/v1/project-status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"project_name", "last_updated"}
    assert data["project_name"] == "晚托班 AI 教师提效系统"


def test_panel_overview_page_does_not_show_raw_sections() -> None:
    with TestClient(create_dashboard_app()) as client:
        response = client.get("/project-status")

    assert response.status_code == 200
    text = response.text
    assert "进入协作中心" not in text
    assert "D 盘" not in text
    assert "进入项目文档" not in text
    assert "进入技术评审" not in text
    assert "/project-status/stages/P1" not in text
    assert "交付线 ·" in text or "MVP-A · 管理运营底座" in text


def test_panel_quality_page_has_no_links_to_raw_details() -> None:
    with TestClient(create_dashboard_app()) as client:
        response = client.get("/project-status/tests")

    assert response.status_code == 200
    text = response.text
    assert "/project-status/test-runs/" not in text
    assert "/project-status/defects/" not in text
    assert "/project-status/stages/" not in text
    assert "辅助 UI 自动化" in text


def test_frozen_safe_endpoints_remain_available_in_panel() -> None:
    with TestClient(create_dashboard_app()) as client:
        dashboard = client.get("/api/v1/project-status/dashboard")
        evidence = client.get(
            "/api/v1/project-status/dashboard/delivery-lines/"
            "mvp-b-daily-record-closure/evidence/PRD-CHANGE-20260811-002"
        )
        automation = client.get("/api/v1/project-status/test-automation")

    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["delivery_lines"]
    assert evidence.status_code == 200
    assert "document_path" not in json.dumps(evidence.json(), ensure_ascii=False)
    assert automation.status_code == 200


def test_panel_pages_do_not_leak_sensitive_markers() -> None:
    """Panel pages must not expose paths, environments, credentials or business data."""
    with TestClient(create_dashboard_app()) as client:
        pages = {
            "overview": client.get("/project-status"),
            "quality": client.get("/project-status/tests"),
            "automation": client.get("/project-status/tests/automation"),
        }

    for name, response in pages.items():
        assert response.status_code == 200, name
        lowered = response.text.lower()
        for forbidden in (
            "d:/",
            "d:\\",
            "c:/",
            "c:\\",
            "password",
            "密码",
            "学生数据",
            "原始日志",
        ):
            assert forbidden not in lowered, (name, forbidden)


def _real_project_payload() -> dict:
    project_path = Path(__file__).resolve().parents[2] / "project-status.json"
    return json.loads(project_path.read_text(encoding="utf-8"))


def _project_root_with_payload(tmp_path, payload: dict) -> Path:
    root = tmp_path / "panel-root"
    (root / "app" / "static").mkdir(parents=True)
    (root / "app" / "templates").mkdir(parents=True)
    repo_root = Path(__file__).resolve().parents[2]
    for line in payload.get("delivery_lines", []):
        for evidence in line.get("evidence_links", []):
            document_path = evidence.get("document_path")
            if not document_path:
                continue
            source = repo_root / "docs" / document_path
            if not source.is_file():
                continue
            target = root / "docs" / document_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "project-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return root


def test_dashboard_projection_rejects_undeclared_scope_fields(tmp_path) -> None:
    payload = _real_project_payload()
    payload["delivery_lines"][0]["scope_in"][0]["secret_path"] = "C:/secret.env"
    root = _project_root_with_payload(tmp_path, payload)

    from app.services.project_status import load_project_status

    with pytest.raises(ValueError, match="undeclared fields"):
        load_project_status(project_root=root)


def test_dashboard_projection_rejects_undeclared_blocker_fields(tmp_path) -> None:
    payload = _real_project_payload()
    payload["delivery_lines"][0]["open_blockers"][0]["local_path"] = (
        "D:/sensitive/run.log"
    )
    root = _project_root_with_payload(tmp_path, payload)

    from app.services.project_status import load_project_status

    with pytest.raises(ValueError, match="undeclared fields"):
        load_project_status(project_root=root)

    with TestClient(create_dashboard_app(root)) as client:
        response = client.get("/api/v1/project-status/dashboard")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["delivery_lines"] == []
    assert data["warnings"]
    assert "D:/sensitive" not in json.dumps(data, ensure_ascii=False)
    assert "local_path" not in json.dumps(data, ensure_ascii=False)


@pytest.mark.parametrize(
    ("target", "injected_key"),
    [
        ("contract_state", "author"),
        ("candidate_version", "commit_sha"),
        ("runtime_gate", "evidence_path"),
    ],
)
def test_dashboard_projection_rejects_undeclared_state_fields(
    tmp_path, target: str, injected_key: str
) -> None:
    payload = _real_project_payload()
    payload["delivery_lines"][0][target][injected_key] = "D:/leak.txt"
    root = _project_root_with_payload(tmp_path, payload)

    from app.services.project_status import load_project_status

    with pytest.raises(ValueError, match="undeclared fields"):
        load_project_status(project_root=root)


def test_dashboard_projection_rejects_undeclared_evidence_fields(tmp_path) -> None:
    payload = _real_project_payload()
    payload["delivery_lines"][0]["evidence_links"][0]["raw_content"] = (
        "D:/raw/evidence.log"
    )
    root = _project_root_with_payload(tmp_path, payload)

    from app.services.project_status import load_project_status

    with pytest.raises(ValueError, match="undeclared fields"):
        load_project_status(project_root=root)


def test_dashboard_projection_whitelists_nested_structures() -> None:
    """Even valid data is rebuilt key-by-key in the safe projection."""
    payload = _real_project_payload()

    from app.services.project_status import build_delivery_dashboard_view

    view = build_delivery_dashboard_view(payload)
    line = view["delivery_lines"][0]

    assert set(line["scope_in"][0]) == {"id", "label"}
    assert set(line["contract_state"]) == {"status", "safe_summary"}
    assert set(line["candidate_version"]) == {"status", "safe_summary"}
    assert set(line["runtime_gate"]) == {"status", "safe_summary"}
    assert set(line["open_blockers"][0]) == {
        "id",
        "title",
        "status",
        "next_action",
        "updated_at",
        "evidence_refs",
    }
    evidence_keys = set(line["evidence_links"][0])
    assert "document_path" not in evidence_keys
    assert "reference" not in evidence_keys
    assert "href" in evidence_keys
