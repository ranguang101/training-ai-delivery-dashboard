"""R3 轻量监控安全边界：脏数据不 500、字段闭合、受控详情 404 与面板隔离。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration._dashboard_fixtures import (
    make_panel_root,
    make_r3_root,
    minimal_project_status,
    r3_fact,
    r3_line,
    r3_target,
    r3_test_run_target,
)
from tools.project_dashboard.main import create_dashboard_app

WORKSPACE_URL = "/api/v1/project-status/dashboard/r3/workspaces/development"
EVIDENCE_URL = "/api/v1/project-status/dashboard/r3/evidence"


@pytest.fixture(autouse=True)
def freeze_r3_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the date-sensitive demo fixture deterministic across calendar days."""

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            current = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
            return current.astimezone(tz) if tz else current.replace(tzinfo=None)

    monkeypatch.setattr("app.services.delivery_monitor.datetime", FrozenDateTime)
    monkeypatch.setattr("tests.integration._dashboard_fixtures.datetime", FrozenDateTime)


def _client(
    tmp_path,
    dashboard_r3: dict | None = None,
    *,
    seed: Callable[[Path], None] | None = None,
) -> TestClient:
    root = tmp_path / "panel-root"
    if seed is not None:
        seed(root)
    root = make_r3_root(root, dashboard_r3=dashboard_r3, with_templates=True)
    return TestClient(create_dashboard_app(root))


def _codes(data: dict) -> list[str]:
    return [w["code"] for w in data["warnings"]]


def _write_raw(root, content: str) -> None:
    (root / "project-status.json").write_text(content, encoding="utf-8")


def test_corrupt_json_returns_safe_empty(tmp_path) -> None:
    root = make_panel_root(tmp_path, with_templates=True)
    _write_raw(root, "{not valid json")
    response = TestClient(create_dashboard_app(root)).get(WORKSPACE_URL)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "R3_DATA_UNAVAILABLE" in _codes(data)
    assert data["line_options"] == []
    assert data["cards"]["progress"]["facts"] == []
    assert data["cards"]["conclusion"]["items"] == []


def test_array_root_returns_safe_empty(tmp_path) -> None:
    root = make_panel_root(tmp_path, with_templates=True)
    _write_raw(root, "[1, 2, 3]")
    response = TestClient(create_dashboard_app(root)).get(WORKSPACE_URL)
    assert response.status_code == 200
    assert "R3_DATA_UNAVAILABLE" in _codes(response.json()["data"])


def test_unknown_section_fields_return_safe_empty(tmp_path) -> None:
    with _client(tmp_path, {"delivery_lines": [], "unknown_root_key": []}) as client:
        data = client.get(WORKSPACE_URL).json()["data"]
        assert "R3_DATA_UNAVAILABLE" in _codes(data)
        assert data["cards"]["progress"]["facts"] == []


def test_wrong_section_types_return_safe_empty(tmp_path) -> None:
    with _client(tmp_path, {"delivery_lines": {}}) as client:
        data = client.get(WORKSPACE_URL).json()["data"]
        assert "R3_DATA_UNAVAILABLE" in _codes(data)


def test_missing_section_returns_safe_empty(tmp_path) -> None:
    root = make_panel_root(
        tmp_path, project_status=minimal_project_status(), with_templates=True
    )
    response = TestClient(create_dashboard_app(root)).get(WORKSPACE_URL)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "R3_SECTION_MISSING" in _codes(data)
    assert data["cards"]["conclusion"]["items"] == []


def test_demo_project_serves_real_r3_content() -> None:
    """默认演示夹具必须起机即有三条交付线与五类事实，供前端真实联调。"""
    with TestClient(create_dashboard_app()) as client:
        response = client.get(WORKSPACE_URL)
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["line_options"]) == 3
        all_facts = data["cards"]["progress"]["facts"] + data["cards"][
            "gates_and_blockers"
        ]["facts"]
        assert {"completed", "in_progress", "next_action", "blocked", "candidate"} == {
            f["fact_type"] for f in all_facts
        }
        available = [e for e in data["cards"]["checked_evidence"]["items"] if e["available"]]
        assert available
        assert all("D:" not in json.dumps(fact, ensure_ascii=False) for fact in all_facts)


def test_dirty_fact_skipped_others_projected(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [
            r3_fact("FACT-GOOD", fact_type="in_progress", workspace_ids=["development"]),
            r3_fact("FACT-BAD", fact_type="not-a-type", workspace_ids=["development"]),
        ],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = client.get(WORKSPACE_URL).json()["data"]
        fact_ids = [f["fact_id"] for f in data["cards"]["progress"]["facts"]]
        assert fact_ids == ["FACT-GOOD"]
        assert "R3_INVALID_FACT" in _codes(data)


def test_unknown_nested_fields_do_not_leak(tmp_path) -> None:
    bad_fact = r3_fact("FACT-BAD", fact_type="in_progress", workspace_ids=["development"])
    bad_fact["href"] = "https://example.com/secret"
    bad_fact["file_path"] = "C:\\Users\\secret\\data.json"
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [bad_fact],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        response = client.get(WORKSPACE_URL)
        body = json.dumps(response.json(), ensure_ascii=False)
        assert "example.com" not in body
        assert "secret" not in body
        assert "C:\\Users" not in body
        assert "R3_INVALID_FACT" in _codes(response.json()["data"])


def test_evidence_ref_with_url_or_path_is_dropped(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                fact_type="in_progress",
                evidence_refs=[
                    {"type": "document", "id": "DOC-1", "href": "file:///etc/passwd"},
                    {"type": "document", "id": "file:///etc/passwd"},
                ],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [r3_target("document", "DOC-1")],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        response = client.get(WORKSPACE_URL)
        body = json.dumps(response.json(), ensure_ascii=False)
        assert "file:" not in body
        fact = response.json()["data"]["cards"]["progress"]["facts"][0]
        assert fact["evidence_refs"] == []


def test_evidence_detail_returns_only_allowed_fields(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }

    def seed(root: Path) -> None:
        dashboard_r3["evidence_targets"].append(
            r3_test_run_target(root, run_id="RUN-P1-20260809-000003")
        )

    with _client(tmp_path, dashboard_r3, seed=seed) as client:
        response = client.get(f"{EVIDENCE_URL}/test_run/RUN-P1-20260809-000003")
        assert response.status_code == 200
        data = response.json()["data"]
        assert set(data) == {
            "type",
            "id",
            "title",
            "status",
            "owner_role",
            "owner_role_label",
            "verified_at",
            "safe_summary",
            "related_evidence_ids",
            "available",
            "unavailable_reason",
        }
        assert data["available"] is True


def test_evidence_detail_registered_but_unresolvable_is_unavailable(tmp_path) -> None:
    """登记表标 valid 但无真实受控资产：详情仍安全返回，但不视为可用。"""
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [],
        "evidence_targets": [r3_target("test_run", "RUN-ONLY")],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        response = client.get(f"{EVIDENCE_URL}/test_run/RUN-ONLY")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["available"] is False
        assert data["unavailable_reason"] == "证据尚未登记"


def test_incompatible_evidence_purpose_is_safely_dropped(tmp_path) -> None:
    """P8-min 只能标注在 test_run，不能借交接单伪造运行门槛。"""
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [
            r3_fact(
                "FACT-A-1",
                fact_type="completed",
                evidence_refs=[{"type": "handoff", "id": "HO-P8-PRETEND"}],
                workspace_ids=["development"],
            )
        ],
        "evidence_targets": [
            r3_target("handoff", "HO-P8-PRETEND", purpose="p8_min_runtime")
        ],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        data = client.get(WORKSPACE_URL).json()["data"]
        assert "R3_INVALID_TARGET" in _codes(data)
        fact = data["cards"]["progress"]["facts"][0]
        assert fact["status"] == "pending_check"


def test_evidence_detail_unknown_or_illegal_returns_stable_404(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [],
        "evidence_targets": [r3_target("document", "DOC-1")],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        for url in (
            f"{EVIDENCE_URL}/document/DOC-UNKNOWN",
            f"{EVIDENCE_URL}/evil/DOC-1",
            f"{EVIDENCE_URL}/document/C:%5Cwindows",
        ):
            response = client.get(url)
            assert response.status_code == 404
            assert response.json()["detail"] == "R3_EVIDENCE_NOT_FOUND"
        # 路径注入在框架层被拒绝：稳定 404 且不回显注入内容
        injected = client.get(f"{EVIDENCE_URL}/document/..%2F..%2Fetc%2Fpasswd")
        assert injected.status_code == 404
        assert "passwd" not in json.dumps(injected.json(), ensure_ascii=False)


def test_evidence_detail_missing_section_returns_stable_404(tmp_path) -> None:
    root = make_panel_root(
        tmp_path, project_status=minimal_project_status(), with_templates=True
    )
    response = TestClient(create_dashboard_app(root)).get(f"{EVIDENCE_URL}/document/DOC-1")
    assert response.status_code == 404
    assert response.json()["detail"] == "R3_EVIDENCE_NOT_FOUND"


def test_panel_project_root_isolation_for_r3(tmp_path) -> None:
    root_a = make_r3_root(
        tmp_path / "a",
        dashboard_r3={
            "delivery_lines": [r3_line(name="项目 A 交付线")],
            "delivery_facts": [
                r3_fact("FACT-A-1", fact_type="in_progress", workspace_ids=["development"])
            ],
            "evidence_targets": [],
            "declared_candidate_combinations": [],
        },
    )
    root_b = make_r3_root(
        tmp_path / "b",
        dashboard_r3={
            "delivery_lines": [r3_line(name="项目 B 交付线")],
            "delivery_facts": [
                r3_fact("FACT-B-1", fact_type="in_progress", workspace_ids=["development"])
            ],
            "evidence_targets": [],
            "declared_candidate_combinations": [],
        },
    )
    with TestClient(create_dashboard_app(root_a)) as client_a, TestClient(
        create_dashboard_app(root_b)
    ) as client_b:
        data_a = client_a.get(WORKSPACE_URL).json()["data"]
        data_b = client_b.get(WORKSPACE_URL).json()["data"]

    assert [f["fact_id"] for f in data_a["cards"]["progress"]["facts"]] == ["FACT-A-1"]
    assert [f["fact_id"] for f in data_b["cards"]["progress"]["facts"]] == ["FACT-B-1"]
    assert "FACT-B-1" not in json.dumps(data_a, ensure_ascii=False)
    assert "FACT-A-1" not in json.dumps(data_b, ensure_ascii=False)


def test_old_raw_apis_still_closed_in_panel_mode(tmp_path) -> None:
    root = make_r3_root(tmp_path, dashboard_r3={}, with_templates=True)
    with TestClient(create_dashboard_app(root)) as client:
        assert client.get("/api/v1/project-status/development").status_code == 404
        assert client.get("/api/v1/project-status/collaboration").status_code == 404
        assert client.get("/project-status/documents").status_code == 404
        assert client.get("/api/v1/project-status/tests").status_code == 404
        sync = client.get("/api/v1/project-status").json()["data"]
        assert set(sync) == {"project_name", "last_updated", "revision"}
        assert sync["revision"]


def test_legacy_dashboard_endpoint_is_removed_from_r3(tmp_path) -> None:
    dashboard_r3 = {
        "delivery_lines": [r3_line()],
        "delivery_facts": [r3_fact("FACT-A-1", fact_type="in_progress")],
        "evidence_targets": [],
        "declared_candidate_combinations": [],
    }
    with _client(tmp_path, dashboard_r3) as client:
        legacy = client.get("/api/v1/project-status/dashboard")
        assert legacy.status_code == 404
        assert "FACT-A-1" not in legacy.text
