"""R4 质量需求生命周期的服务端投影、准出降级与兼容回归。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from tools.project_dashboard.main import DEFAULT_DASHBOARD_DATA_ROOT, create_dashboard_app


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "demo-project"
    shutil.copytree(DEFAULT_DASHBOARD_DATA_ROOT, root)
    return root


def _client(root: Path) -> TestClient:
    return TestClient(create_dashboard_app(root))


def _payload(root: Path) -> dict:
    return json.loads((root / "project-status.json").read_text(encoding="utf-8"))


def _write(root: Path, payload: dict) -> None:
    (root / "project-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_three_requirements_follow_fixed_order_and_four_card_boundary(tmp_path) -> None:
    root = _root(tmp_path)
    with _client(root) as client:
        response = client.get("/api/v1/project-status/quality-requirements")
        assert response.status_code == 200
        data = response.json()["data"]
        assert [item["quality_requirement_id"] for item in data["requirements"]] == [
            "QR-MVP-A",
            "QR-MVP-B-MANUAL",
            "QR-MVP-B-TEXT-AI",
        ]
        assert set(data["cards"]) == {
            "formal_cases",
            "assisted_automation",
            "defects",
            "final_report",
        }
        assert data["cards"]["formal_cases"]["total"] == 2
        assert data["cards"]["formal_cases"]["passed"] == 2
        assert (
            data["cards"]["assisted_automation"]["boundary_statement"]
            == "辅助自动化，不等于正式准出"
        )
        assert data["cards"]["final_report"]["can_enter_product_acceptance"] is True


def test_detail_projects_traceability_without_raw_report_or_path(tmp_path) -> None:
    root = _root(tmp_path)
    with _client(root) as client:
        response = client.get(
            "/api/v1/project-status/quality-requirements/QR-MVP-B-MANUAL",
            params={"line": "mvp-b-manual-daily-record"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        sections = data["sections"]
        assert sections["traceability"]["case_ids"] == ["MVP-B-TC-001", "MVP-B-TC-002"]
        assert sections["traceability"]["report_ids"] == ["RUN-MVP-B-20260813-001000"]
        assert sections["cases"][0]["latest_execution"]["execution_status"] == "passed"
        encoded = json.dumps(data, ensure_ascii=False)
        assert "D:\\" not in encoded
        assert "file:" not in encoded.lower()
        assert "independent-test-report.md" not in encoded


def test_line_mismatch_is_empty_and_never_falls_back_to_other_requirement(tmp_path) -> None:
    root = _root(tmp_path)
    with _client(root) as client:
        response = client.get(
            "/api/v1/project-status/quality-requirements",
            params={
                "requirement": "QR-MVP-A",
                "line": "mvp-b-manual-daily-record",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["state"] == "mismatch"
        assert data["selected_requirement"] is None
        assert data["cards"]["formal_cases"]["total"] == 0
        assert any(item["code"] == "QW_REQUIREMENT_LINE_MISMATCH" for item in data["warnings"])


def test_auxiliary_automation_never_supplies_formal_case_or_readiness(tmp_path) -> None:
    root = _root(tmp_path)
    payload = _payload(root)
    section = payload["quality_workspace_r4"]
    section["formal_cases"] = [
        item
        for item in section["formal_cases"]
        if item["quality_requirement_id"] != "QR-MVP-B-MANUAL"
    ]
    section["case_executions"] = [
        item for item in section["case_executions"] if not item["case_id"].startswith("MVP-B-")
    ]
    _write(root, payload)
    with _client(root) as client:
        data = client.get(
            "/api/v1/project-status/quality-requirements",
            params={"requirement": "QR-MVP-B-MANUAL", "line": "mvp-b-manual-daily-record"},
        ).json()["data"]
        assert data["cards"]["formal_cases"]["total"] == 0
        assert data["cards"]["assisted_automation"]["passed_pending_human"] == 1
        assert data["selected_requirement"]["can_enter_product_acceptance"] is False
        assert any(item["code"] == "QW_NO_FORMAL_CASES" for item in data["warnings"])


def test_open_high_defect_and_candidate_mismatch_block_product_acceptance(tmp_path) -> None:
    root = _root(tmp_path)
    payload = _payload(root)
    section = payload["quality_workspace_r4"]
    requirement = next(
        item
        for item in section["requirements"]
        if item["quality_requirement_id"] == "QR-MVP-B-MANUAL"
    )
    requirement["candidate_status"] = "inconsistent"
    section["defects"].append(
        {
            "defect_id": "BUG-MVP-B-OPEN",
            "quality_requirement_id": "QR-MVP-B-MANUAL",
            "severity": "high",
            "status": "open",
            "case_ids": ["MVP-B-TC-001"],
            "report_ids": [],
            "candidate_ref": "MVP-B-9e38e599",
            "retest_status": "待修复",
            "safe_summary": "受控缺陷摘要。",
        }
    )
    _write(root, payload)
    with _client(root) as client:
        data = client.get(
            "/api/v1/project-status/quality-requirements",
            params={"requirement": "QR-MVP-B-MANUAL", "line": "mvp-b-manual-daily-record"},
        ).json()["data"]
        assert data["selected_requirement"]["can_enter_product_acceptance"] is False
        assert data["selected_requirement"]["status"] == "blocked"
        assert data["cards"]["defects"]["has_open_high_priority"] is True
        assert data["cards"]["final_report"]["safe_summary"] == "候选不一致，状态待核对"


def test_missing_section_is_safe_empty_projection_and_unknown_requirement_is_404(tmp_path) -> None:
    root = _root(tmp_path)
    payload = _payload(root)
    payload.pop("quality_workspace_r4")
    _write(root, payload)
    with _client(root) as client:
        empty = client.get("/api/v1/project-status/quality-requirements")
        assert empty.status_code == 200
        assert empty.json()["data"]["requirements"] == []
        assert empty.json()["data"]["selected_requirement"] is None
        assert (
            empty.json()["data"]["cards"]["final_report"]["can_enter_product_acceptance"] is False
        )
        missing = client.get("/api/v1/project-status/quality-requirements/QR-NOT-FOUND")
        assert missing.status_code == 404
        assert missing.json()["detail"] == "QUALITY_REQUIREMENT_NOT_FOUND"


def test_quality_workspace_pages_preserve_safe_r3_routes_and_use_controlled_r4_client(
    tmp_path,
) -> None:
    root = _root(tmp_path)
    with _client(root) as client:
        for path in (
            "/project-status/tests",
            "/project-status/tests/requirements?requirement=QR-MVP-A&line=mvp-a-management-foundation",
            "/project-status/tests/requirements/QR-MVP-B-MANUAL?line=mvp-b-manual-daily-record",
            "/project-status/workspaces/testing",
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert "项目交付看板" in response.text
        page = client.get("/project-status/tests/requirements")
        assert "data-quality-requirements" in page.text
        assert "quality-lifecycle.js" in page.text
        assert "/api/v1/project-status/quality-requirements" not in page.text
