"""R3 轻量监控投影：交付线、工作区、四卡归属、候选校验与降级。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration._dashboard_fixtures import (
    make_r3_root,
    r3_candidate,
    r3_combo,
    r3_fact,
    r3_handoff_target,
    r3_line,
    r3_report_run_target,
    r3_target,
    r3_test_run_target,
    r3_time,
)
from tools.project_dashboard.main import create_dashboard_app

LINE_A = "mvp-a-management-foundation"
LINE_B = "mvp-b-manual-daily-record"
LINE_C = "mvp-b-text-ai-enhancement"

WORKSPACES = ("collaboration", "development", "frontend", "testing")


def _client(
    tmp_path: Path,
    dashboard_r3: dict,
    *,
    seed: Callable[[Path], None] | None = None,
) -> TestClient:
    root = tmp_path / "panel-root"
    if seed is not None:
        seed(root)
    root = make_r3_root(root, dashboard_r3=dashboard_r3, with_templates=True)
    return TestClient(create_dashboard_app(root))


def _workspace(client: TestClient, workspace_id: str, line: str | None = None) -> dict:
    response = client.get(
        f"/api/v1/project-status/dashboard/r3/workspaces/{workspace_id}",
        params={"line": line} if line else None,
    )
    assert response.status_code == 200
    return response.json()["data"]


def _codes(data: dict) -> list[str]:
    return [w["code"] for w in data["warnings"]]


def test_three_lines_four_workspaces_project_safely(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, name="MVP-A 管理运营底座"),
            r3_line(LINE_B, name="MVP-B v0.1 人工每日记录闭环"),
            r3_line(LINE_C, name="MVP-B 文字学情整理 AI 增强"),
        ],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "in_progress", workspace_ids=["collaboration"]),
            r3_fact("FACT-B-1", LINE_B, "in_progress", workspace_ids=["development"]),
            r3_fact("FACT-C-1", LINE_C, "in_progress", workspace_ids=["testing"]),
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        for workspace_id in WORKSPACES:
            data = _workspace(client, workspace_id)
            assert data["workspace"]["id"] == workspace_id
            assert data["workspace"]["label"]
            assert len(data["line_options"]) == 3
            assert data["selected_line"] is None
            assert set(data["cards"]) == {
                "conclusion",
                "progress",
                "gates_and_blockers",
                "checked_evidence",
            }
            fact_ids = [f["fact_id"] for f in data["cards"]["progress"]["facts"]]
            expected = {
                "collaboration": ["FACT-A-1"],
                "development": ["FACT-B-1"],
                "frontend": [],
                "testing": ["FACT-C-1"],
            }[workspace_id]
            assert fact_ids == expected


def test_line_filter_and_unknown_params(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A, name="MVP-A"), r3_line(LINE_B, name="MVP-B")],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "completed", workspace_ids=["development"]),
            r3_fact("FACT-B-1", LINE_B, "completed", workspace_ids=["development"]),
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development", line=LINE_A)
        assert data["selected_line"] == {"id": LINE_A, "label": "MVP-A"}
        fact_ids = [f["fact_id"] for f in data["cards"]["progress"]["facts"]]
        assert fact_ids == ["FACT-A-1"]
        assert [i["delivery_line_id"] for i in data["cards"]["conclusion"]["items"]] == [LINE_A]

        unknown_line = client.get(
            "/api/v1/project-status/dashboard/r3/workspaces/development",
            params={"line": "unknown-line"},
        )
        assert unknown_line.status_code == 404
        assert unknown_line.json()["detail"] == "R3_LINE_NOT_FOUND"

        unknown_workspace = client.get(
            "/api/v1/project-status/dashboard/r3/workspaces/unknown",
        )
        assert unknown_workspace.status_code == 404
        assert unknown_workspace.json()["detail"] == "R3_WORKSPACE_NOT_FOUND"


def test_same_fact_consistent_across_workspaces(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                status="verified",
                owner_role="testing",
                verified_at=r3_time(hours_ago=5),
                evidence_refs=[{"type": "test_run", "id": "RUN-P1-20260809-000001"}],
                workspace_ids=["collaboration", "development", "testing"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(root, run_id="RUN-P1-20260809-000001", owner_role="testing")
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        seen = {}
        for workspace_id in ("collaboration", "development", "testing"):
            data = _workspace(client, workspace_id)
            fact = data["cards"]["progress"]["facts"][0]
            seen[workspace_id] = {
                "fact_id": fact["fact_id"],
                "status": fact["status"],
                "owner_role": fact["owner_role"],
                "verified_at": fact["verified_at"],
                "evidence_refs": fact["evidence_refs"],
            }
        assert seen["collaboration"] == seen["development"] == seen["testing"]


def test_card_attribution_strict(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(f"FACT-{index}", LINE_A, fact_type, workspace_ids=["development"])
            for index, fact_type in enumerate(
                ("completed", "in_progress", "next_action", "blocked", "candidate")
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        progress_types = {f["fact_type"] for f in data["cards"]["progress"]["facts"]}
        gate_types = {f["fact_type"] for f in data["cards"]["gates_and_blockers"]["facts"]}
        assert progress_types == {"completed", "in_progress", "next_action"}
        assert gate_types == {"blocked", "candidate"}
        assert progress_types.isdisjoint(gate_types)


def test_candidate_missing_fields_projects_pending(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                candidate=r3_candidate(backend="待提供", candidate_status="fixed"),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [r3_combo(LINE_A)],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["gates_and_blockers"]["facts"][0]
        assert fact["candidate_status"] == "pending"
        assert fact["candidate_status_label"] == "候选信息待补齐"
        assert "backend_candidate" in fact["missing_fields"]
        assert fact["status"] == "pending_check"
        assert "R3_CANDIDATE_INCOMPLETE" in _codes(data)


def test_candidate_migration_not_applicable_can_be_fixed(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                evidence_refs=[{"type": "test_run", "id": "RUN-P1-20260809-000001"}],
                candidate=r3_candidate(migration="不适用", candidate_status="fixed"),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [
            r3_combo(LINE_A, migration="不适用", handoff="HO-1")
        ],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(root, run_id="RUN-P1-20260809-000001")
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        fact = _workspace(client, "development")["cards"]["gates_and_blockers"]["facts"][0]
        assert fact["candidate_status"] == "fixed"
        assert fact["candidate_status_label"] == "候选组合已固定"
        assert fact["status"] == "verified"
        assert fact["missing_fields"] == []
        assert fact["conflict_sources"] == []


def test_candidate_declared_combo_match_projects_fixed(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                candidate=r3_candidate(
                    backend="b1", frontend="f1", handoff="HO-1", candidate_status="fixed"
                ),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [r3_combo(LINE_A)],
    }
    with _client(tmp_path, dashboard_r3) as client:
        fact = _workspace(client, "development")["cards"]["gates_and_blockers"]["facts"][0]
        assert fact["candidate_status"] == "fixed"


def test_candidate_combo_mismatch_projects_inconsistent(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_product_acceptance=True, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                candidate=r3_candidate(backend="b9", candidate_status="fixed"),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [r3_combo(LINE_A, backend="b1")],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["gates_and_blockers"]["facts"][0]
        assert fact["candidate_status"] == "inconsistent"
        assert fact["candidate_status_label"] == "候选不一致，状态待核对"
        assert fact["summary"] == "候选不一致，状态待核对"
        assert fact["status"] == "pending_check"
        assert fact["conflict_sources"]
        assert "R3_CANDIDATE_UNMATCHED" in _codes(data)


def test_candidate_declared_pending_with_complete_fields_is_inconsistent(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                candidate=r3_candidate(candidate_status="pending"),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [r3_combo(LINE_A)],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["gates_and_blockers"]["facts"][0]
        assert fact["candidate_status"] == "inconsistent"
        assert fact["status"] == "pending_check"
        assert "R3_CANDIDATE_STATUS_MISMATCH" in _codes(data)


def test_inconsistent_candidate_blocks_line_flags(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_product_acceptance=True, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                candidate=r3_candidate(backend="b9", candidate_status="fixed"),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [r3_combo(LINE_A, backend="b1")],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_product_acceptance"] is False
        assert line_item["can_enter_controlled_trial"] is False
        assert "R3_LINE_CANDIDATE_INCONSISTENT" in _codes(data)


def test_stale_fact_projects_stale(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "in_progress",
                verified_at=r3_time(hours_ago=73),
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["progress"]["facts"][0]
        assert fact["status"] == "stale"
        assert "R3_FACT_STALE" in _codes(data)
        assert fact["summary"]
        assert fact["verified_at"]


def test_missing_verified_at_warns_without_fabrication(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "in_progress",
                verified_at="not-a-date",
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["progress"]["facts"][0]
        assert fact["status"] == "verified"
        assert "R3_FACT_VERIFIED_AT_MISSING" in _codes(data)


def test_line_invalid_verified_at_warns_without_fabrication(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A, verified_at="2026-08-23")],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "in_progress", workspace_ids=["development"])
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["verified_at"] is None
        assert "R3_LINE_VERIFIED_AT_MISSING" in _codes(data)


def test_future_verified_at_never_projects_as_verified_or_valid(tmp_path) -> None:
    """未来时间不能借由静态演示数据伪装成当前已核对证据。"""
    future = r3_time(hours_ago=-1)
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A, verified_at=future)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                verified_at=future,
                evidence_refs=[{"type": "test_run", "id": "RUN-P1-20260809-000001"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(
                root,
                run_id="RUN-P1-20260809-000001",
                verified_at=future,
            )
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        fact = data["cards"]["progress"]["facts"][0]
        evidence = data["cards"]["checked_evidence"]["items"][0]

        assert line_item["verified_at"] is None
        assert fact["verified_at"] is None
        assert fact["status"] == "pending_check"
        assert evidence["verified_at"] is None
        assert evidence["status"] == "missing"
        assert evidence["available"] is False
        assert evidence["unavailable_reason"] == "核对日期待补录"
        assert "R3_LINE_VERIFIED_AT_FUTURE" in _codes(data)
        assert "R3_FACT_VERIFIED_AT_FUTURE" in _codes(data)

        detail = client.get(
            "/api/v1/project-status/dashboard/r3/evidence/test_run/"
            "RUN-P1-20260809-000001"
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["status"] == "missing"
        assert detail.json()["data"]["verified_at"] is None
        assert detail.json()["data"]["available"] is False


def test_completed_without_evidence_degrades_to_pending_check(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "completed", workspace_ids=["development"]),
            r3_fact(
                "FACT-A-2",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "document", "id": "DOC-MISSING"}],
                workspace_ids=["development"],
            ),
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        facts = {f["fact_id"]: f for f in data["cards"]["progress"]["facts"]}
        assert facts["FACT-A-1"]["status"] == "pending_check"
        assert facts["FACT-A-2"]["status"] == "pending_check"
        assert "R3_FACT_EVIDENCE_MISSING" in _codes(data)
        evidence = data["cards"]["checked_evidence"]["items"][0]
        assert evidence["available"] is False
        assert evidence["unavailable_reason"] == "证据尚未登记"


def test_report_style_run_resolves_without_summary(tmp_path) -> None:
    """独立测试报告类运行目录（如 RUN-MVP-A-20260812-001000）以报告文件为登记依据。"""
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "test_run", "id": "RUN-MVP-A-20260812-001000"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_report_run_target(root, run_id="RUN-MVP-A-20260812-001000")
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["progress"]["facts"][0]
        assert fact["status"] == "verified"
        evidence = data["cards"]["checked_evidence"]["items"][0]
        assert evidence["available"] is True


def test_run_dir_with_invalid_summary_does_not_resolve(tmp_path) -> None:
    """summary.json 存在但未通过完整性校验的运行不得作为有效证据。"""
    import json

    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "test_run", "id": "RUN-BAD-1"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [r3_target("test_run", "RUN-BAD-1")],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        run_dir = root / "reports" / "test-runs" / "RUN-BAD-1"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            json.dumps({"id": "RUN-BAD-1", "git_dirty": True}, ensure_ascii=False),
            encoding="utf-8",
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["progress"]["facts"][0]
        assert fact["status"] == "pending_check"
        evidence = data["cards"]["checked_evidence"]["items"][0]
        assert evidence["available"] is False


def test_registered_but_unresolvable_evidence_is_unavailable(tmp_path) -> None:
    """登记表标 valid 但稳定编号无真实受控资产时，证据不可用且不得支撑完成结论。"""
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_product_acceptance=True, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "test_run", "id": "RUN-ONLY"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [r3_target("test_run", "RUN-ONLY")],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        fact = data["cards"]["progress"]["facts"][0]
        assert fact["status"] == "pending_check"
        assert "R3_FACT_EVIDENCE_MISSING" in _codes(data)
        evidence = data["cards"]["checked_evidence"]["items"][0]
        assert evidence["available"] is False
        assert evidence["unavailable_reason"] == "证据尚未登记"
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_product_acceptance"] is False
        assert line_item["can_enter_controlled_trial"] is False


def test_fictional_test_run_does_not_prop_up_trial(tmp_path) -> None:
    """复现验收问题1：虚构 test_run 不得放行可试用结论（DASH-LITE-003）。"""
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(
                LINE_A,
                delivery_status="ready_for_trial",
                can_enter_product_acceptance=True,
                can_enter_controlled_trial=True,
            )
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "test_run", "id": "RUN-ONLY"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [r3_target("test_run", "RUN-ONLY")],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_product_acceptance"] is False
        assert line_item["can_enter_controlled_trial"] is False
        assert line_item["delivery_status"] == "ready_for_trial"
        codes = _codes(data)
        assert "R3_LINE_TRIAL_UNVERIFIED" in codes
        assert "R3_LINE_FLAG_UNVERIFIED" in codes


def test_fixed_candidate_without_evidence_degrades(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-CAND-1",
                LINE_A,
                "candidate",
                workspace_ids=["development"],
                candidate=r3_candidate(candidate_status="fixed"),
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [r3_combo(LINE_A)],
    }
    with _client(tmp_path, dashboard_r3) as client:
        fact = _workspace(client, "development")["cards"]["gates_and_blockers"]["facts"][0]
        assert fact["candidate_status"] == "fixed"
        assert fact["status"] == "pending_check"
        assert fact["candidate_status_label"] == "候选组合已固定"


def test_no_facts_for_line_degrades_truthfully(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A), r3_line(LINE_B)],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "in_progress", workspace_ids=["development"])
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development", line=LINE_B)
        assert data["cards"]["progress"]["facts"] == []
        assert data["cards"]["gates_and_blockers"]["facts"] == []
        assert data["cards"]["checked_evidence"]["items"] == []
        assert [i["delivery_line_id"] for i in data["cards"]["conclusion"]["items"]] == [LINE_B]
        assert "R3_LINE_NO_FACTS" in _codes(data)


def test_checked_evidence_aggregates_and_dedupes(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line(LINE_A)],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "test_run", "id": "RUN-P1-20260809-000001"}],
                workspace_ids=["development"],
            ),
            r3_fact(
                "FACT-A-2",
                LINE_A,
                "in_progress",
                evidence_refs=[
                    {"type": "test_run", "id": "RUN-P1-20260809-000001"},
                    {"type": "test_run", "id": "RUN-P1-20260809-000002"},
                ],
                workspace_ids=["development"],
            ),
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(root, run_id="RUN-P1-20260809-000001")
        )
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(
                root, run_id="RUN-P1-20260809-000002", verified_at=r3_time(hours_ago=80)
            )
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        data = _workspace(client, "development")
        items = data["cards"]["checked_evidence"]["items"]
        assert len(items) == 2
        by_key = {(i["type"], i["id"]): i for i in items}
        assert by_key[("test_run", "RUN-P1-20260809-000001")]["available"] is True
        assert by_key[("test_run", "RUN-P1-20260809-000001")]["unavailable_reason"] is None
        assert by_key[("test_run", "RUN-P1-20260809-000002")]["available"] is False
        assert by_key[("test_run", "RUN-P1-20260809-000002")]["unavailable_reason"] == "待复核"


def test_line_flags_degrade_without_evidence(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_product_acceptance=True, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "in_progress", workspace_ids=["development"])
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_product_acceptance"] is False
        assert line_item["can_enter_controlled_trial"] is False
        codes = _codes(data)
        assert "R3_LINE_FLAG_UNVERIFIED" in codes
        assert "R3_LINE_TRIAL_UNVERIFIED" in codes


def test_trial_requires_product_acceptance_and_runtime_evidence(tmp_path) -> None:
    """仅有运行证据（无产品人工验收结论）时不得显示可试用。"""
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[{"type": "test_run", "id": "RUN-P1-20260809-000001"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(root, run_id="RUN-P1-20260809-000001")
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_controlled_trial"] is False
        assert "R3_LINE_TRIAL_UNVERIFIED" in _codes(data)


def test_ready_for_trial_requires_pair(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(
                LINE_A,
                delivery_status="ready_for_trial",
                can_enter_product_acceptance=True,
                can_enter_controlled_trial=True,
            )
        ],
        "delivery_facts": [
            r3_fact("FACT-A-1", LINE_A, "in_progress", workspace_ids=["development"])
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_controlled_trial"] is False
        assert line_item["delivery_status"] == "ready_for_trial"
        assert line_item["delivery_status_label"] == "可试用"
        assert "R3_LINE_TRIAL_UNVERIFIED" in _codes(data)


def test_line_flags_kept_with_valid_evidence_pair(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_product_acceptance=True, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[
                    {"type": "test_run", "id": "RUN-P1-20260809-000001"},
                    {"type": "handoff", "id": "HO-ACCEPT-1"},
                ],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(
                root,
                run_id="RUN-P1-20260809-000001",
                purpose="p8_min_runtime",
            )
        )
        dashboard_r3["evidence_targets"].append(
            r3_handoff_target(
                root,
                handoff_id="HO-ACCEPT-1",
                purpose="product_acceptance",
            )
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        line_item = _workspace(client, "development")["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_product_acceptance"] is True
        assert line_item["can_enter_controlled_trial"] is True


def test_unrelated_test_run_cannot_substitute_for_p8_min_runtime(tmp_path) -> None:
    """普通独立测试与产品验收交接齐全，也不能被误判为可试用。"""
    dashboard_r3 = {
        "delivery_lines": [
            r3_line(LINE_A, can_enter_product_acceptance=True, can_enter_controlled_trial=True)
        ],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                LINE_A,
                "completed",
                evidence_refs=[
                    {"type": "test_run", "id": "RUN-P1-20260809-000001"},
                    {"type": "handoff", "id": "HO-ACCEPT-1"},
                ],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(root, run_id="RUN-P1-20260809-000001")
        )
        dashboard_r3["evidence_targets"].append(
            r3_handoff_target(
                root,
                handoff_id="HO-ACCEPT-1",
                purpose="product_acceptance",
            )
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        data = _workspace(client, "development")
        line_item = data["cards"]["conclusion"]["items"][0]
        assert line_item["can_enter_product_acceptance"] is True
        assert line_item["can_enter_controlled_trial"] is False
        assert "R3_LINE_TRIAL_UNVERIFIED" in _codes(data)
