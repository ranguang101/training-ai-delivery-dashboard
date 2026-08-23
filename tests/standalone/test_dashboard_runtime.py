"""Standalone R3 startup and loopback boundary checks."""

import pytest
from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app
from tools.project_dashboard.run import resolve_loopback_host


def test_default_demo_starts_with_r3_safe_projection_only() -> None:
    with TestClient(create_dashboard_app()) as client:
        workspace = client.get("/api/v1/project-status/dashboard/r3/workspaces/collaboration")
        assert workspace.status_code == 200
        data = workspace.json()["data"]
        assert len(data["line_options"]) == 3
        assert set(data["cards"]) == {
            "conclusion",
            "progress",
            "gates_and_blockers",
            "checked_evidence",
        }

        sync = client.get("/api/v1/project-status")
        assert sync.status_code == 200
        assert set(sync.json()["data"]) == {"project_name", "last_updated"}

        # R2 raw-data and auxiliary-operation surfaces are not part of R3.
        assert client.get("/api/v1/project-status/dashboard").status_code == 404
        assert client.get("/project-status/tests/automation").status_code == 404


def _workspace(client: TestClient, workspace: str, line: str) -> dict:
    response = client.get(
        f"/api/v1/project-status/dashboard/r3/workspaces/{workspace}",
        params={"line": line},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_pending_candidate_fixture_is_in_memory_only() -> None:
    with TestClient(create_dashboard_app(r3_test_fixture="pending-candidate")) as client:
        data = _workspace(client, "development", "mvp-b-manual-daily-record")
        candidate = data["cards"]["gates_and_blockers"]["facts"][0]
        assert candidate["candidate_status"] == "pending"
        assert candidate["candidate_status_label"] == "候选信息待补齐"
        assert candidate["status"] == "pending_check"
        conclusion = data["cards"]["conclusion"]["items"][0]
        assert conclusion["current_conclusion"] == "候选未固定，当前不可独立测试；状态待核对"
        assert conclusion["current_candidate_summary"] == "候选信息待补齐"
        assert conclusion["can_enter_product_acceptance"] is False
        assert conclusion["can_enter_controlled_trial"] is False

    with TestClient(create_dashboard_app()) as client:
        data = _workspace(client, "development", "mvp-b-manual-daily-record")
        candidate = data["cards"]["gates_and_blockers"]["facts"][0]
        assert candidate["candidate_status"] == "fixed"


def test_inconsistent_candidate_fixture_projects_conflict() -> None:
    with TestClient(create_dashboard_app(r3_test_fixture="inconsistent-candidate")) as client:
        data = _workspace(client, "development", "mvp-b-manual-daily-record")
        candidate = data["cards"]["gates_and_blockers"]["facts"][0]
        assert candidate["candidate_status"] == "inconsistent"
        assert candidate["summary"] == "候选不一致，状态待核对"
        assert candidate["status"] == "pending_check"
        conclusion = data["cards"]["conclusion"]["items"][0]
        assert conclusion["current_conclusion"] == "候选不一致，状态待核对"
        assert conclusion["current_candidate_summary"] == "候选不一致，状态待核对"
        assert conclusion["can_enter_product_acceptance"] is False


def test_unavailable_evidence_fixture_disables_target() -> None:
    with TestClient(create_dashboard_app(r3_test_fixture="unavailable-evidence")) as client:
        data = _workspace(client, "testing", "mvp-b-manual-daily-record")
        evidence = data["cards"]["checked_evidence"]["items"][0]
        assert evidence["available"] is False
        assert evidence["status"] == "missing"
        assert evidence["unavailable_reason"] == "证据暂不可查看"
        conclusion = data["cards"]["conclusion"]["items"][0]
        assert conclusion["current_conclusion"] == "核对证据不可用或日期待补录，当前状态待核对"
        assert conclusion["can_enter_product_acceptance"] is False


def test_empty_line_fixture_projects_honest_empty_state() -> None:
    with TestClient(create_dashboard_app(r3_test_fixture="empty-line")) as client:
        data = _workspace(client, "testing", "r3-test-empty-line")
        assert data["selected_line"]["label"] == "R3 UI 空态验证"
        assert data["cards"]["progress"]["facts"] == []
        assert any(item["code"] == "R3_LINE_NO_FACTS" for item in data["warnings"])


def test_stale_and_missing_date_fixture_degrades_facts() -> None:
    with TestClient(create_dashboard_app(r3_test_fixture="stale-and-missing-dates")) as client:
        stale = _workspace(client, "testing", "mvp-b-manual-daily-record")
        stale_fact = stale["cards"]["progress"]["facts"][0]
        assert stale_fact["status"] == "stale"
        stale_conclusion = stale["cards"]["conclusion"]["items"][0]
        assert stale_conclusion["current_conclusion"] == "部分核对信息已过期，当前状态待复核"
        assert stale_conclusion["can_enter_product_acceptance"] is False

        missing = _workspace(client, "development", "mvp-b-text-ai-enhancement")
        missing_fact = next(
            fact
            for fact in missing["cards"]["progress"]["facts"]
            if fact["fact_id"] == "FACT-MVPC-002"
        )
        assert missing_fact["verified_at"] is None
        assert missing_fact["status"] == "pending_check"
        missing_conclusion = missing["cards"]["conclusion"]["items"][0]
        assert (
            missing_conclusion["current_conclusion"]
            == "核对证据不可用或日期待补录，当前状态待核对"
        )
        assert missing_conclusion["can_enter_product_acceptance"] is False
        assert any(item["code"] == "R3_FACT_VERIFIED_AT_MISSING" for item in missing["warnings"])


def test_workspace_503_fault_is_opt_in() -> None:
    with TestClient(create_dashboard_app(test_fault="r3-workspace-503")) as client:
        response = client.get("/api/v1/project-status/dashboard/r3/workspaces/testing")
        assert response.status_code == 503
        assert response.json()["detail"] == "R3_TEST_WORKSPACE_UNAVAILABLE"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_loopback_hosts_are_allowed(host: str) -> None:
    assert resolve_loopback_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com"])
def test_non_loopback_hosts_are_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="DASHBOARD_LOOPBACK_ONLY"):
        resolve_loopback_host(host)
