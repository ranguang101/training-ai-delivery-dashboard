"""F-04: --project-root must flow into every asset-reading layer."""

import json

from fastapi.testclient import TestClient

from app.services import test_management
from tests.integration._dashboard_fixtures import (
    make_panel_root,
    minimal_project_status,
    write_valid_run,
)
from tools.project_dashboard.main import create_dashboard_app


def _line_payload(line_id: str, name: str) -> dict:
    return {
        "id": line_id,
        "delivery_track": "track",
        "name": name,
        "display_label": "D1 · 范围已确认",
        "source_role": "product",
        "verified_at": "2026-08-12",
        "evidence_level": "D1",
        "delivery_status": "planning",
        "summary": "safe summary",
        "updated_at": "2026-08-12T00:00:00+08:00",
        "scope_in": [{"id": "A", "label": "范围 A"}],
        "scope_out": [],
        "contract_state": {"status": "frozen", "safe_summary": "冻结"},
        "candidate_version": {"status": "not_fixed", "safe_summary": "未固定"},
        "runtime_gate": {"status": "not_assessed", "safe_summary": "未评估"},
        "evidence_links": [],
        "open_blockers": [],
    }


def _two_roots(tmp_path):
    root_a = make_panel_root(
        tmp_path / "a",
        project_status=minimal_project_status(
            project_name="项目 A",
            last_updated="2026-08-20T01:00:00+08:00",
            delivery_lines=[_line_payload("line-a", "交付线 A")],
            stages=[{"code": "P1", "title": "阶段 A", "requirements_count": 0}],
        ),
        with_templates=True,
        template_marker="ROOT-A-TEMPLATE-MARKER",
        static_marker="marker-a.txt",
    )
    root_b = make_panel_root(
        tmp_path / "b",
        project_status=minimal_project_status(
            project_name="项目 B",
            last_updated="2026-08-20T02:00:00+08:00",
            delivery_lines=[_line_payload("line-b", "交付线 B")],
            stages=[{"code": "P1", "title": "阶段 B", "requirements_count": 0}],
        ),
        with_templates=True,
        template_marker="ROOT-B-TEMPLATE-MARKER",
        static_marker="marker-b.txt",
    )
    return root_a, root_b


def test_dashboard_data_is_isolated_between_project_roots(tmp_path) -> None:
    root_a, root_b = _two_roots(tmp_path)
    app_a = create_dashboard_app(root_a)
    app_b = create_dashboard_app(root_b)

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        data_a = client_a.get("/api/v1/project-status/dashboard").json()["data"]
        data_b = client_b.get("/api/v1/project-status/dashboard").json()["data"]
        sync_a = client_a.get("/api/v1/project-status").json()["data"]
        sync_b = client_b.get("/api/v1/project-status").json()["data"]

    assert [line["id"] for line in data_a["delivery_lines"]] == ["line-a"]
    assert [line["id"] for line in data_b["delivery_lines"]] == ["line-b"]
    assert "line-b" not in json.dumps(data_a, ensure_ascii=False)
    assert "line-a" not in json.dumps(data_b, ensure_ascii=False)
    assert sync_a == {"project_name": "项目 A", "last_updated": "2026-08-20T01:00:00+08:00"}
    assert sync_b == {"project_name": "项目 B", "last_updated": "2026-08-20T02:00:00+08:00"}


def test_test_run_assets_are_isolated_between_project_roots(tmp_path) -> None:
    root_a, root_b = _two_roots(tmp_path)
    write_valid_run(root_b, run_id="RUN-P1-20260809-000002")

    runs_a = test_management.load_test_runs("P1", project_root=root_a)
    runs_b = test_management.load_test_runs("P1", project_root=root_b)

    assert runs_a == []
    assert [run["id"] for run in runs_b] == ["RUN-P1-20260809-000002"]

    with TestClient(create_dashboard_app(root_a)) as client_a:
        page_a = client_a.get("/project-status/tests")
    with TestClient(create_dashboard_app(root_b)) as client_b:
        page_b = client_b.get("/project-status/tests")

    assert page_a.status_code == 200 and page_b.status_code == 200
    assert "RUN-P1-20260809-000002" not in page_a.text
    # Recent-run rows are hidden in the panel, but the total must still differ.
    assert "项目 B" in page_b.text
    assert "项目 A" in page_a.text


def test_templates_and_static_follow_the_project_root(tmp_path) -> None:
    root_a, root_b = _two_roots(tmp_path)
    app_a = create_dashboard_app(root_a)
    app_b = create_dashboard_app(root_b)

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        page_a = client_a.get("/project-status")
        page_b = client_b.get("/project-status")
        static_a = client_a.get("/static/marker-a.txt")
        static_b_missing = client_b.get("/static/marker-a.txt")
        static_b = client_b.get("/static/marker-b.txt")

    assert page_a.status_code == 200 and page_b.status_code == 200
    assert "ROOT-A-TEMPLATE-MARKER" in page_a.text
    assert "ROOT-B-TEMPLATE-MARKER" in page_b.text
    assert "ROOT-B-TEMPLATE-MARKER" not in page_a.text
    assert static_a.status_code == 200
    assert static_a.text == "marker:marker-a.txt"
    assert static_b.status_code == 200
    assert static_b.text == "marker:marker-b.txt"
    assert static_b_missing.status_code == 404


def test_case_design_and_automation_read_their_own_root(tmp_path) -> None:
    root_a, root_b = _two_roots(tmp_path)
    automation_dir = root_b / "docs" / "testing"
    automation_dir.mkdir(parents=True, exist_ok=True)
    (automation_dir / "automation-run-index.json").write_text(
        json.dumps({"schema_version": "1.0", "runs": []}), encoding="utf-8"
    )
    tasks_dir = root_b / "docs" / "testing" / "case-generation"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "case-generation-runs.json").write_text(
        json.dumps({"runs": []}, ensure_ascii=False), encoding="utf-8"
    )

    with TestClient(create_dashboard_app(root_a)) as client_a:
        automation_a = client_a.get("/api/v1/project-status/test-automation")
        case_design_a = client_a.get("/api/v1/project-status/tests/case-design")
    with TestClient(create_dashboard_app(root_b)) as client_b:
        automation_b = client_b.get("/api/v1/project-status/test-automation")
        case_design_b = client_b.get("/api/v1/project-status/tests/case-design")

    assert automation_a.json()["data"]["runs"] == []
    assert automation_b.json()["data"]["runs"] == []
    assert "未提供" in automation_a.json()["data"]["warnings"][0]
    assert case_design_a.json()["data"]["tasks"] == []
    assert case_design_b.json()["data"]["tasks"] == []
    assert "尚未提供" in case_design_a.json()["data"]["warnings"][0]


def test_evidence_validation_uses_the_panel_root(tmp_path) -> None:
    """A document evidence must resolve inside the panel root, not the repo."""
    root_a, _ = _two_roots(tmp_path)
    docs_dir = root_a / "docs" / "requirements" / "product"
    docs_dir.mkdir(parents=True)
    (docs_dir / "panel-own.md").write_text("# 面板自有文档", encoding="utf-8")

    payload = json.loads(
        (root_a / "project-status.json").read_text(encoding="utf-8")
    )
    payload["delivery_lines"][0]["evidence_links"] = [
        {
            "id": "PANEL-DOC-001",
            "label": "面板文档",
            "kind": "document",
            "evidence_level": "D1",
            "status": "current",
            "display_label": "D1 · 文档",
            "source_role": "product",
            "verified_at": "2026-08-12",
            "checked_at": "2026-08-12",
            "safe_summary": "面板自有文档",
            "document_path": "requirements/product/panel-own.md",
        }
    ]
    (root_a / "project-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    with TestClient(create_dashboard_app(root_a)) as client:
        response = client.get("/api/v1/project-status/dashboard")

    assert response.status_code == 200
    assert response.json()["data"]["delivery_lines"][0]["evidence_links"][0]["id"] == (
        "PANEL-DOC-001"
    )
