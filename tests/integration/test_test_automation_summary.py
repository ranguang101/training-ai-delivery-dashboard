"""Safety and isolation checks for the auxiliary UI automation summary API."""

import json

from fastapi.testclient import TestClient

from app.services import test_management
from tools.project_dashboard.main import create_dashboard_app


def _write_index(path, runs) -> None:
    path.write_text(
        json.dumps({"schema_version": "1.0", "runs": runs}, ensure_ascii=False),
        encoding="utf-8",
    )


def _valid_run() -> dict:
    return {
        "run_id": "AUX-P1-TC-021-20260815-001",
        "source_case_id": "P1-TC-021",
        "case_version": "1.0",
        "tool_commit": "118f23bffde97bae9c21d75c0016491308ee432b",
        "tested_project_commit": "bc5e8a91b95ef347d1e75462f0c7218751c34de7",
        "automation_status": "assisted_completed_pending_review",
        "assertion_total": 11,
        "assertion_failed": 0,
        "manual_items_count": 2,
        "cleanup_status": "passed",
        "executed_at": None,
        "review_status": "pending_testing_review",
        "classification": "auxiliary_ui_automation",
        "governance_statement": test_management.AUTOMATION_GOVERNANCE_STATEMENT,
        "evidence_ids": ["AUTOMATION-SUMMARY-P1-TC-021-001"],
    }


def _panel_root(tmp_path, index_payload=None, index_name="automation-run-index.json"):
    """A minimal project root for the standalone panel under test."""
    root = tmp_path / "panel-root"
    testing_dir = root / "docs" / "testing"
    testing_dir.mkdir(parents=True)
    (root / "app" / "static").mkdir(parents=True)
    if index_payload is not None:
        (testing_dir / index_name).write_text(
            json.dumps(index_payload, ensure_ascii=False), encoding="utf-8"
        )
    return root


def test_auxiliary_automation_summary_is_safe_and_does_not_change_formal_totals(
    tmp_path,
) -> None:
    root = _panel_root(
        tmp_path, {"schema_version": "1.0", "runs": [_valid_run()]}
    )
    formal_totals_before = test_management.build_test_center(
        {"stages": [{"code": "P1", "title": "账号与权限", "requirements_count": 0}]}
    )["totals"]

    with TestClient(create_dashboard_app(root)) as client:
        listing = client.get("/api/v1/project-status/test-automation")
        detail = client.get(
            "/api/v1/project-status/test-automation/runs/AUX-P1-TC-021-20260815-001"
        )
        evidence = client.get(
            "/api/v1/project-status/test-automation/runs/"
            "AUX-P1-TC-021-20260815-001/evidence/"
            "AUTOMATION-SUMMARY-P1-TC-021-001"
        )

    formal_totals_after = test_management.build_test_center(
        {"stages": [{"code": "P1", "title": "账号与权限", "requirements_count": 0}]}
    )["totals"]
    assert formal_totals_after == formal_totals_before
    assert listing.status_code == 200
    payload = listing.json()["data"]
    assert payload["summary"] == {
        "listed_runs": 1,
        "formal_case_statistics_changed": False,
        "release_decision_changed": False,
    }
    assert payload["runs"] == [
        {
            "run_id": "AUX-P1-TC-021-20260815-001",
            "source_case_id": "P1-TC-021",
            "case_version": "1.0",
            "automation_status": "assisted_completed_pending_review",
            "automation_status_label": "辅助执行完成 · 待测试复核",
            "assertion_total": 11,
            "assertion_failed": 0,
            "manual_items_count": 2,
            "cleanup_status": "passed",
            "cleanup_status_label": "清理通过",
            "executed_at": None,
            "review_status": "pending_testing_review",
            "review_status_label": "待测试负责人复核",
            "classification": "auxiliary_ui_automation",
            "classification_label": "辅助 UI 自动化",
            "governance_statement": test_management.AUTOMATION_GOVERNANCE_STATEMENT,
            "detail_href": "/api/v1/project-status/test-automation/runs/"
            "AUX-P1-TC-021-20260815-001",
        }
    ]
    assert detail.status_code == 200
    assert detail.json()["data"]["tool_commit"] == _valid_run()["tool_commit"]
    assert detail.json()["data"]["tested_project_commit"] == _valid_run()[
        "tested_project_commit"
    ]
    assert detail.json()["data"]["evidence_links"] == [
        {
            "id": "AUTOMATION-SUMMARY-P1-TC-021-001",
            "kind": "controlled_summary",
            "label": "受控辅助自动化摘要",
            "safe_summary": (
                "P1-TC-021：11 项断言，0 项失败；"
                "原始报告、截图和运行器输出不在管理面板展示。"
            ),
            "href": "/api/v1/project-status/test-automation/runs/"
            "AUX-P1-TC-021-20260815-001/evidence/"
            "AUTOMATION-SUMMARY-P1-TC-021-001",
        }
    ]
    assert evidence.status_code == 200
    rendered = json.dumps(
        {"listing": listing.json(), "detail": detail.json(), "evidence": evidence.json()},
        ensure_ascii=False,
    ).lower()
    for forbidden in ("d:\\wta", "report.json", "password", "学生", "日志"):
        assert forbidden not in rendered


def test_auxiliary_automation_rejects_external_paths_and_degrades_safely(tmp_path) -> None:
    unsafe_run = {
        **_valid_run(),
        "raw_report_path": r"D:\wta\p1-clean\report.json",
    }
    root = _panel_root(
        tmp_path, {"schema_version": "1.0", "runs": [unsafe_run]}
    )

    with TestClient(create_dashboard_app(root)) as client:
        listing = client.get("/api/v1/project-status/test-automation")
        missing = client.get("/api/v1/project-status/test-automation/runs/not-a-run")
        evidence = client.get(
            "/api/v1/project-status/test-automation/runs/"
            "AUX-P1-TC-021-20260815-001/evidence/not-an-evidence"
        )

    assert listing.status_code == 200
    data = listing.json()["data"]
    assert data["runs"] == []
    assert data["warnings"] == ["存在不符合受控摘要格式的条目，已不对外展示。"]
    assert "D:\\wta" not in json.dumps(data, ensure_ascii=False)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "TEST_AUTOMATION_RUN_NOT_FOUND"
    assert evidence.status_code == 404
    assert evidence.json()["detail"] == "TEST_AUTOMATION_EVIDENCE_NOT_FOUND"


def test_auxiliary_automation_missing_index_returns_safe_empty_list(tmp_path) -> None:
    root = _panel_root(tmp_path)

    with TestClient(create_dashboard_app(root)) as client:
        response = client.get("/api/v1/project-status/test-automation")

    assert response.status_code == 200
    assert response.json()["data"]["runs"] == []
    assert response.json()["data"]["warnings"] == [
        "未提供辅助自动化运行摘要；当前不显示任何辅助执行结果。"
    ]
