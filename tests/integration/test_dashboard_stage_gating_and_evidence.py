"""F-03: stage summaries and D5/D6 evidence must be truthful and traceable."""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import project_status as project_status_service
from app.services import test_management
from tests.integration._dashboard_fixtures import (
    make_panel_root,
    minimal_project_status,
    write_valid_run,
)
from tools.project_dashboard.main import create_dashboard_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _seed_cases(root: Path) -> None:
    cases_dir = root / "docs" / "testing" / "cases"
    cases_dir.mkdir(parents=True)
    (cases_dir / "P1.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": f"P1-TC-{number:03}",
                        "title": f"接口契约 {number}",
                        "type": "api",
                        "priority": "P0",
                        "automation_status": "automated",
                        "automation": {"framework": "pytest"},
                    }
                    for number in range(1, 4)
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _seed_defects(root: Path, defects: list) -> None:
    defects_path = root / "docs" / "testing" / "defects.json"
    defects_path.parent.mkdir(parents=True, exist_ok=True)
    defects_path.write_text(
        json.dumps({"defects": defects}, ensure_ascii=False), encoding="utf-8"
    )


def _stage_root(tmp_path, *, git_dirty: bool = False, counts=None, defects=None) -> Path:
    root = make_panel_root(
        tmp_path,
        project_status=minimal_project_status(
            stages=[{"code": "P1", "title": "账号与权限", "requirements_count": 0}]
        ),
        with_templates=True,
    )
    _seed_cases(root)
    write_valid_run(root, git_dirty=git_dirty, counts=counts)
    if defects is not None:
        _seed_defects(root, defects)
    return root


def _high_open_defect() -> dict:
    return {
        "id": "BUG-P1-001",
        "stage": "P1",
        "severity": "high",
        "status": "confirmed",
        "title": "接口权限缺陷",
    }


def test_open_high_severity_defect_blocks_passed(tmp_path) -> None:
    root = _stage_root(tmp_path, defects=[_high_open_defect()])

    summary = test_management.stage_test_summary("P1", project_root=root)

    assert summary["status"] == "blocked"
    assert summary["blocking_defects"] == 1
    assert "高/严重缺陷" in summary["note"]


def test_closed_high_severity_defect_does_not_block(tmp_path) -> None:
    closed = {**_high_open_defect(), "status": "closed"}
    root = _stage_root(tmp_path, defects=[closed])

    summary = test_management.stage_test_summary("P1", project_root=root)

    assert summary["status"] == "passed"
    assert summary["blocking_defects"] == 0


def test_dirty_latest_run_cannot_yield_passed(tmp_path) -> None:
    root = _stage_root(tmp_path, git_dirty=True)

    summary = test_management.stage_test_summary("P1", project_root=root)

    assert summary["status"] != "passed"
    assert summary["status"] == "in_progress"


def test_inconsistent_counts_run_cannot_yield_passed(tmp_path) -> None:
    lying_counts = {
        "executed": 3,
        "passed": 3,
        "failed": 2,
        "blocked": 0,
        "not_executed": 0,
    }
    root = _stage_root(tmp_path, counts=lying_counts)

    summary = test_management.stage_test_summary("P1", project_root=root)

    assert summary["status"] != "passed"
    assert summary["status"] == "in_progress"


def _delivery_line_payload() -> dict:
    payload = json.loads(
        (PROJECT_ROOT / "project-status.json").read_text(encoding="utf-8")
    )
    line = copy.deepcopy(payload["delivery_lines"][0])
    line.update(
        {
            "evidence_level": "D5",
            "contract_state": {"status": "frozen", "safe_summary": "契约已冻结"},
            "candidate_version": {"status": "fixed", "safe_summary": "候选已固定"},
            "runtime_gate": {"status": "evidence_ready", "safe_summary": "证据已齐"},
            "open_blockers": [],
            "evidence_links": [
                {
                    "id": "INDEPENDENT-TEST-001",
                    "label": "独立测试运行",
                    "kind": "test_run",
                    "evidence_level": "D5",
                    "status": "passed",
                    "display_label": "D5 · 独立测试通过",
                    "source_role": "testing",
                    "verified_at": "2026-08-12",
                    "checked_at": "2026-08-12",
                    "safe_summary": "固定提交独立测试通过",
                    "reference": "RUN-P1-20260809-000001",
                }
            ],
        }
    )
    return {"delivery_lines": [line]}


def test_fake_test_run_reference_cannot_claim_d5(tmp_path) -> None:
    payload = _delivery_line_payload()
    payload["delivery_lines"][0]["evidence_links"][0]["reference"] = (
        "RUN-P1-99991231-000000"
    )
    root = make_panel_root(tmp_path, project_status=payload)

    with pytest.raises(ValueError, match="controlled test run"):
        project_status_service.load_project_status(project_root=root)

    with TestClient(create_dashboard_app(root)) as client:
        response = client.get("/api/v1/project-status/dashboard")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["delivery_lines"] == []
    assert data["warnings"]


def test_dirty_referenced_run_cannot_claim_d5(tmp_path) -> None:
    root = make_panel_root(tmp_path)
    write_valid_run(root, git_dirty=True)
    payload = _delivery_line_payload()
    (root / "project-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="controlled test run"):
        project_status_service.load_project_status(project_root=root)


def test_real_controlled_run_enables_d5(tmp_path) -> None:
    root = make_panel_root(tmp_path)
    write_valid_run(root)
    payload = _delivery_line_payload()
    (root / "project-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    project = project_status_service.load_project_status(project_root=root)
    view = project_status_service.build_delivery_dashboard_view(
        project, project_root=root
    )
    assert view["delivery_lines"][0]["evidence_level"] == "D5"

    with TestClient(create_dashboard_app(root)) as client:
        response = client.get("/api/v1/project-status/dashboard")

    assert response.status_code == 200
    assert response.json()["data"]["delivery_lines"][0]["evidence_level"] == "D5"


def test_fake_handoff_reference_cannot_claim_d6(tmp_path) -> None:
    payload = _delivery_line_payload()
    line = payload["delivery_lines"][0]
    line["evidence_level"] = "D6"
    line["runtime_gate"]["status"] = "passed"
    line["evidence_links"][0].update(
        {
            "evidence_level": "D6",
            "kind": "handoff",
            "reference": "HO-DT-999",
        }
    )
    root = make_panel_root(tmp_path, project_status=payload)

    with pytest.raises(ValueError, match="registered handoff"):
        project_status_service.load_project_status(project_root=root)


def test_auxiliary_automation_never_changes_formal_stage_summary(tmp_path) -> None:
    root = make_panel_root(
        tmp_path,
        project_status=minimal_project_status(
            stages=[{"code": "P1", "title": "账号与权限", "requirements_count": 0}]
        ),
    )
    _seed_cases(root)
    write_valid_run(root)
    before = test_management.stage_test_summary("P1", project_root=root)

    index_path = root / "docs" / "testing" / "automation-run-index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "runs": [
                    {
                        "run_id": "AUX-P1-TC-021-20260815-001",
                        "source_case_id": "P1-TC-021",
                        "case_version": "1.0",
                        "tool_commit": "118f23bffde97bae9c21d75c0016491308ee432b",
                        "tested_project_commit": (
                            "bc5e8a91b95ef347d1e75462f0c7218751c34de7"
                        ),
                        "automation_status": "assisted_completed_pending_review",
                        "assertion_total": 11,
                        "assertion_failed": 0,
                        "manual_items_count": 2,
                        "cleanup_status": "passed",
                        "executed_at": None,
                        "review_status": "pending_testing_review",
                        "classification": "auxiliary_ui_automation",
                        "governance_statement": (
                            test_management.AUTOMATION_GOVERNANCE_STATEMENT
                        ),
                        "evidence_ids": ["AUTOMATION-SUMMARY-P1-TC-021-001"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    after = test_management.stage_test_summary("P1", project_root=root)
    for key in ("status", "total", "executed", "passed", "failed", "open_defects"):
        assert after[key] == before[key], key
