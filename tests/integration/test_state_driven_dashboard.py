"""STATE-AC-001—009: fixture-driven dashboard contract regression."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.routers.project_status import router as project_status_router
from app.services.dashboard_contract import (
    STATUS_CATALOG,
    STATUS_VALUES,
    delivery_line_relation_warnings,
)
from tests.integration._dashboard_fixtures import (
    delivery_line_fixture,
    make_panel_root,
    quality_workspace_fixture,
    state_driven_project_status,
)
from tools.project_dashboard.main import create_dashboard_app

LINE_FIELDS = {
    "delivery_line_id", "name", "scope_summary", "status", "evidence_level",
    "contract_state", "candidate_version", "runtime_gate", "display_label",
    "summary", "source_role", "source_role_label", "verified_at", "updated_at",
    "blocker_count", "next_action",
}
ROLE_FIELDS = {"name", "status", "current", "next", "waiting_for", "integration_status"}
FORBIDDEN_TOKENS = {
    "document_path", "source_path", "raw_log", "logs", "secret", "api_key",
    "database_url", "environment", "business_plaintext", "owned_paths",
}


def _client(tmp_path: Path, payload: dict) -> TestClient:
    root = make_panel_root(tmp_path, project_status=payload, with_templates=True)
    return TestClient(create_dashboard_app(root))


@pytest.mark.parametrize("level", ["D1", "D3", "D5", "D6"])
def test_evidence_level_and_gate_relationships_are_fixture_driven(
    tmp_path: Path, level: str
) -> None:
    """STATE-AC-002/004: no real line is assumed to remain at one D level."""
    line = delivery_line_fixture(level)
    assert delivery_line_relation_warnings(line, field="delivery_lines[0]") == []

    with _client(tmp_path, state_driven_project_status(line)) as client:
        response = client.get("/api/v1/project-status/lightweight", params={"page": "overview"})

    assert response.status_code == 200
    data = response.json()["data"]
    projected = data["data"]["lines"][0]
    assert projected["evidence_level"]["code"] == level
    assert data["selected_line"]["evidence_level"]["code"] == level
    assert not any(
        item["code"] == "DASHBOARD_EVIDENCE_RELATION_INVALID"
        for item in data["warnings"]
    )


def test_invalid_enum_and_invalid_d5_relation_degrade_with_field_paths(tmp_path: Path) -> None:
    """STATE-AC-003/004: invalid evolution is diagnosable and never successful."""
    line = delivery_line_fixture("D5", candidate_status="not_fixed", runtime_status="open")
    line["delivery_status"] = "future_unregistered_state"
    with _client(tmp_path, state_driven_project_status(line)) as client:
        data = client.get(
            "/api/v1/project-status/lightweight", params={"page": "overview"}
        ).json()["data"]

    projected = data["data"]["lines"][0]
    assert projected["status"] == {"code": "pending_check", "label": "待核对"}
    assert {item["code"] for item in data["warnings"]} >= {
        "DASHBOARD_UNKNOWN_ENUM", "DASHBOARD_EVIDENCE_RELATION_INVALID"
    }
    assert any(
        item.get("field") == "delivery_lines[0].delivery_status"
        for item in data["warnings"]
    )
    assert all(projected[key]["code"] != "passed" for key in ("status", "runtime_gate"))


def test_delivery_line_cannot_claim_less_than_its_evidence_item() -> None:
    """STATE-AC-004: the line level must cover every registered evidence level."""
    line = delivery_line_fixture("D3")
    line["evidence_links"][0]["evidence_level"] = "D4"

    warnings = delivery_line_relation_warnings(line, field="delivery_lines[0]")

    assert warnings[0]["code"] == "DASHBOARD_EVIDENCE_RELATION_INVALID"
    assert "证据项等级不得高于交付线等级" in warnings[0]["safe_message"]


def test_every_registered_enum_has_a_nonempty_safe_display_label() -> None:
    """STATE-AC-003: enum and display-map sets cannot silently drift apart."""
    for field, labels in STATUS_CATALOG.items():
        assert labels, field
        assert set(labels) == STATUS_VALUES[field]
        assert all(isinstance(label, str) and label.strip() for label in labels.values())


def test_quality_counts_follow_fixture_instead_of_current_project_numbers(tmp_path: Path) -> None:
    """STATE-AC-005: Case/execution/type/defect counts are computed from fixtures."""
    quality = quality_workspace_fixture(
        case_statuses=("passed", "passed", "failed", "blocked", "not_executed"),
        automation_kinds=("automated", "manual", "automated", "manual", "manual"),
        defect_statuses=("in_progress", "ready_for_retest", "retest_failed", "closed"),
    )
    payload = state_driven_project_status(delivery_line_fixture("D3"), quality=quality)
    with _client(tmp_path, payload) as client:
        data = client.get(
            "/api/v1/project-status/lightweight", params={"page": "testing"}
        ).json()["data"]["data"]

    assert (data["formal_cases"], data["executed"], data["not_executed"]) == (5, 4, 1)
    assert (data["passed"], data["failed"], data["blocked"]) == (2, 1, 1)
    assert data["automation"] == {"automated": 2, "manual": 3, "assisted_runs": 0}
    assert data["defects"] == {
        "open": 3,
        "total": 4,
        "lifecycle": {
            "in_progress": 1,
            "ready_for_retest": 1,
            "retest_failed": 1,
            "closed": 1,
        },
    }


@pytest.mark.parametrize(
    ("collection", "status_field", "illegal_status"),
    [
        ("formal_cases", "case_status", "future_case_state"),
        ("case_executions", "execution_status", "future_run_state"),
        ("defects", "status", "future_defect_state"),
    ],
)
def test_illegal_quality_status_degrades_and_is_excluded_from_statistics(
    tmp_path: Path,
    collection: str,
    status_field: str,
    illegal_status: str,
) -> None:
    """STATE-AC-003/005: illegal quality states never enter a ready projection."""
    quality = quality_workspace_fixture()
    quality[collection][0][status_field] = illegal_status
    payload = state_driven_project_status(delivery_line_fixture("D3"), quality=quality)

    with _client(tmp_path, payload) as client:
        data = client.get(
            "/api/v1/project-status/lightweight", params={"page": "testing"}
        ).json()["data"]

    assert data["data"]["state"] == "pending_check"
    warning = next(
        item
        for item in data["warnings"]
        if item.get("field") == f"quality_workspace_r4.{collection}[0].{status_field}"
    )
    assert warning["code"] == "DASHBOARD_UNKNOWN_ENUM"
    assert illegal_status not in json.dumps(data, ensure_ascii=False)
    if collection == "formal_cases":
        assert data["data"]["formal_cases"] == 3
    elif collection == "case_executions":
        assert data["data"]["executed"] == 2
    else:
        assert data["data"]["defects"]["total"] == 2
        assert illegal_status not in data["data"]["defects"]["lifecycle"]


@pytest.mark.parametrize("page", ["overview", "product", "frontend", "development", "testing"])
def test_role_projections_use_explicit_allowlists_and_drop_forbidden_fields(
    tmp_path: Path, page: str
) -> None:
    """STATE-AC-006: sensitive source additions cannot flow through by accident."""
    payload = state_driven_project_status(
        delivery_line_fixture("D1"), quality=quality_workspace_fixture()
    )
    payload["roles"]["development"].update({"raw_log": "unsafe", "owned_paths": ["private"]})
    payload["delivery_lines"][0].update({"secret": "unsafe", "document_path": "private"})
    with _client(tmp_path, payload) as client:
        response = client.get("/api/v1/project-status/lightweight", params={"page": page})

    assert response.status_code == 200
    data = response.json()["data"]
    assert all(set(item) <= LINE_FIELDS for item in data["data"].get("lines", []))
    role = data["data"].get("role")
    if role:
        assert set(role) <= ROLE_FIELDS
    encoded = json.dumps(data, ensure_ascii=False).lower()
    assert not any(token in encoded for token in FORBIDDEN_TOKENS)
    assert "unsafe" not in encoded


def test_dashboard_routes_remain_read_only_and_controlled_get_navigation(tmp_path: Path) -> None:
    """STATE-AC-007: no business mutation surface is exposed by the local panel."""
    payload = state_driven_project_status(
        delivery_line_fixture("D3"), quality=quality_workspace_fixture()
    )
    with _client(tmp_path, payload) as client:
        for route in (
            "/project-status", "/project-status/product", "/project-status/frontend",
            "/project-status/development", "/project-status/tests",
        ):
            page = client.get(route)
            assert page.status_code == 200
            lowered = page.text.lower()
            assert "<form" not in lowered
            assert 'method="post"' not in lowered
            assert 'method="delete"' not in lowered
        api_routes = [
            route
            for route in project_status_router.routes
            if getattr(route, "path", "").startswith("/api/v1/project-status")
        ]
        assert api_routes
        assert all(getattr(route, "methods", set()) <= {"GET"} for route in api_routes)


def test_real_project_status_is_structure_only_and_safe() -> None:
    """STATE-AC-001/008/009: one real-data smoke test without fixed instance values."""
    configured_root = os.environ.get("DASHBOARD_REAL_PROJECT_ROOT")
    if not configured_root:
        pytest.skip("set DASHBOARD_REAL_PROJECT_ROOT to run the real-data smoke test")
    project_root = Path(configured_root).resolve()
    if not (project_root / "project-status.json").is_file():
        pytest.fail("DASHBOARD_REAL_PROJECT_ROOT has no project-status.json")
    with TestClient(create_dashboard_app(project_root)) as client:
        response = client.get("/api/v1/project-status/lightweight", params={"page": "overview"})
        page = client.get("/project-status")

    assert response.status_code == 200
    assert page.status_code == 200
    data = response.json()["data"]
    assert isinstance(data["line_options"], list)
    assert all(set(item) == {"id", "label"} for item in data["line_options"])
    encoded = json.dumps(data, ensure_ascii=False).lower()
    assert not any(token in encoded for token in FORBIDDEN_TOKENS)
    assert "d:\\" not in encoded and "file:" not in encoded
