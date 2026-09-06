"""通用交付线详情的关系隔离、状态降级与受控证据回归。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.integration._dashboard_fixtures import (
    make_panel_root,
    make_r3_root,
    minimal_project_status,
)
from tools.project_dashboard.main import create_dashboard_app

LINE_A = "fixture-line-a"
LINE_B = "fixture-line-b"
REVISION_A = "fixture-revision-a"
SOLUTION_A = "fixture-solution-a"
CANDIDATE_A = "fixture-candidate-a"
EVIDENCE_A = "fixture-evidence-a"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _r3_line(line_id: str) -> dict:
    return {
        "delivery_line_id": line_id,
        "name": f"Synthetic line {line_id}",
        "scope_summary": "Fixture-only scope summary",
        "delivery_status": "implementation",
        "current_conclusion": "Fixture-only delivery conclusion",
        "current_candidate_summary": "Fixture candidate is tracked",
        "next_gate_summary": "Fixture next gate",
        "can_enter_product_acceptance": False,
        "can_enter_controlled_trial": False,
        "verified_at": _now(),
    }


def _status(*, detail: dict | None = None, line_ids: list[str] | None = None) -> dict:
    line_ids = line_ids or [LINE_A]
    lines = [_r3_line(line_id) for line_id in line_ids]
    facts = [
        {
            "fact_id": f"fixture-fact-{line_id}",
            "delivery_line_id": line_id,
            "fact_type": "completed",
            "status": "verified",
            "owner_role": "development",
            "verified_at": _now(),
            "summary": "Fixture-only fact summary",
            "evidence_refs": [],
            "workspace_ids": ["collaboration"],
        }
        for line_id in line_ids
    ]
    return {
        "project_name": "Synthetic fixture project",
        "last_updated": _now(),
        "dashboard_r3": {
            "delivery_lines": lines,
            "delivery_facts": facts,
            "evidence_targets": [],
            "declared_candidate_combinations": [],
        },
        **({"delivery_detail": detail} if detail is not None else {}),
    }


def _detail(
    *,
    relation_line_id: str = LINE_A,
    revision_line_id: str = LINE_A,
    solution_line_id: str = LINE_A,
    candidate_line_id: str = LINE_A,
    evidence_verified_at: str | None = None,
    revisions: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "delivery_line_relations": [
            {
                "delivery_line_id": relation_line_id,
                "requirement_revision_refs": [REVISION_A],
                "technical_solution_refs": [SOLUTION_A],
                "candidate_handoff_refs": [CANDIDATE_A],
                "quality_requirement_refs": [],
                "evidence_refs": [{"evidence_type": "technical_review", "evidence_id": EVIDENCE_A}],
            }
        ],
        "requirement_revisions": revisions
        or [
            {
                "revision_id": REVISION_A,
                "delivery_line_id": revision_line_id,
                "revision_label": "Fixture revision",
                "revision_status": "confirmed",
                "effective_at": _now(),
                "change_refs": [],
                "change_summary": "Fixture-only change summary",
                "scope_delta": "Fixture-only scope delta",
                "owner_role": "development",
                "verified_at": _now(),
                "evidence_refs": [],
            }
        ],
        "technical_solutions": [
            {
                "technical_solution_id": SOLUTION_A,
                "delivery_line_id": solution_line_id,
                "revision_id": REVISION_A,
                "solution_type": "service-contract",
                "solution_status": "verified",
                "title": "Fixture technical solution",
                "controlled_summary": "Fixture-only controlled solution summary",
                "owner_role": "development",
                "verified_at": _now(),
                "candidate_refs": [CANDIDATE_A],
                "evidence_refs": [],
            }
        ],
        "candidate_handoffs": [
            {
                "candidate_handoff_id": CANDIDATE_A,
                "delivery_line_id": candidate_line_id,
                "technical_solution_refs": [SOLUTION_A],
                "candidate_type": "fixture-candidate",
                "handoff_items": [
                    {
                        "item_type": "startup-summary",
                        "safe_summary": "Fixture-only handoff summary",
                        "status": "provided",
                    }
                ],
                "candidate_status": "fixed",
                "missing_items": [],
                "conflict_items": [],
                "verified_at": _now(),
                "quality_requirement_refs": [],
                "evidence_refs": [],
            }
        ],
        "quality_links": [],
        "evidence_projections": [
            {
                "evidence_id": EVIDENCE_A,
                "evidence_type": "technical_review",
                "delivery_line_id": LINE_A,
                "safe_title": "Fixture controlled evidence",
                "safe_summary": "Fixture-only evidence summary",
                "source_role": "development",
                "verified_at": evidence_verified_at or _now(),
                "validity_state": "valid",
                "related_object_refs": [{"object_type": "solution", "object_id": SOLUTION_A}],
            }
        ],
    }


def _client(
    tmp_path, *, detail: dict | None = None, line_ids: list[str] | None = None
) -> TestClient:
    root = make_r3_root(
        tmp_path / "panel-root",
        dashboard_r3=None,
        with_templates=True,
    )
    # Replace the helper's empty JSON with a synthetic, parameterized fixture.
    root.joinpath("project-status.json").write_text(
        json.dumps(_status(detail=detail, line_ids=line_ids), ensure_ascii=False),
        encoding="utf-8",
    )
    return TestClient(create_dashboard_app(root))


def test_complete_detail_reuses_line_and_returns_only_safe_projection(tmp_path) -> None:
    with _client(tmp_path, detail=_detail()) as client:
        response = client.get(f"/api/v1/project-status/delivery-lines/{LINE_A}/detail")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["state"] == "ready"
        assert data["delivery_line"]["delivery_line_id"] == LINE_A
        assert data["summary"]["current_revision_id"] == REVISION_A
        assert data["summary"]["technical_solution_count"] == 1
        assert data["summary"]["candidate_handoff_count"] == 1
        assert data["summary"]["evidence_count"] == 1
        assert "file:" not in response.text.lower()
        assert "source_path" not in response.text


def test_missing_detail_section_is_explicitly_unlinked(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get(f"/api/v1/project-status/delivery-lines/{LINE_A}/detail")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["state"] == "unlinked"
        assert data["summary"]["safe_summary"] == "详情资料待关联"
        assert data["warnings"][0]["code"] == "DD_DETAIL_NOT_LINKED"


def test_modern_delivery_line_id_is_accepted_without_r3_copy(tmp_path) -> None:
    root = make_panel_root(
        tmp_path / "modern-root",
        project_status=minimal_project_status(
            delivery_lines=[
                {
                    "id": LINE_A,
                    "name": "Synthetic modern delivery line",
                    "summary": "Modern source summary",
                    "status": "in_progress",
                    "open_blockers": [],
                }
            ]
        ),
        with_templates=True,
    )

    with TestClient(create_dashboard_app(root)) as client:
        response = client.get(f"/api/v1/project-status/delivery-lines/{LINE_A}/detail")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["delivery_line"]["delivery_line_id"] == LINE_A
    assert data["delivery_line"]["name"] == "Synthetic modern delivery line"
    assert data["state"] == "unlinked"
    assert data["warnings"][0]["code"] == "DD_DETAIL_NOT_LINKED"


def test_cross_line_relationship_is_not_projected(tmp_path) -> None:
    detail = _detail(solution_line_id=LINE_B)
    with _client(tmp_path, detail=detail, line_ids=[LINE_A, LINE_B]) as client:
        data = client.get(f"/api/v1/project-status/delivery-lines/{LINE_A}/detail").json()["data"]
        assert data["state"] == "incomplete"
        assert data["sections"]["technical_solutions"] == []
        assert any(item["code"] == "DD_RELATION_MISSING" for item in data["warnings"])


def test_multiple_confirmed_revisions_are_marked_as_conflict(tmp_path) -> None:
    revisions = _detail()["requirement_revisions"]
    revisions.append({**revisions[0], "revision_id": "fixture-revision-b"})
    detail = _detail(revisions=revisions)
    detail["delivery_line_relations"][0]["requirement_revision_refs"].append("fixture-revision-b")
    with _client(tmp_path, detail=detail) as client:
        data = client.get(f"/api/v1/project-status/delivery-lines/{LINE_A}/detail").json()["data"]
        assert data["summary"]["current_revision_id"] is None
        assert any(item["code"] == "DD_REVISION_CONFLICT" for item in data["warnings"])


def test_stale_evidence_is_explicitly_degraded(tmp_path) -> None:
    stale = (datetime.now(UTC) - timedelta(hours=100)).isoformat(timespec="seconds")
    with _client(tmp_path, detail=_detail(evidence_verified_at=stale)) as client:
        data = client.get(f"/api/v1/project-status/delivery-lines/{LINE_A}/detail").json()["data"]
        assert data["sections"]["evidence"][0]["validity_state"] == "stale"
        assert any(item["code"] == "DD_STALE_DATA" for item in data["warnings"])


def test_evidence_requires_explicit_line_relation_and_has_html_projection(tmp_path) -> None:
    with _client(tmp_path, detail=_detail()) as client:
        evidence_url = (
            f"/api/v1/project-status/delivery-lines/{LINE_A}/evidence/technical_review/{EVIDENCE_A}"
        )
        response = client.get(evidence_url)
        assert response.status_code == 200
        evidence = response.json()["data"]
        assert evidence["evidence_id"] == EVIDENCE_A
        assert "source_path" not in response.text
        assert (
            client.get(
                f"/api/v1/project-status/delivery-lines/{LINE_B}/evidence/technical_review/{EVIDENCE_A}"
            ).status_code
            == 404
        )
        assert (
            client.get("/api/v1/project-status/delivery-lines/unknown-line/detail").status_code
            == 404
        )
        page = client.get(f"/project-status/delivery-lines/{LINE_A}")
        assert page.status_code == 200
        assert "data-delivery-detail" in page.text
        evidence_page = client.get(
            f"/project-status/delivery-lines/{LINE_A}/evidence/technical_review/{EVIDENCE_A}"
        )
        assert evidence_page.status_code == 200
        assert "原始文档、报告、日志" in evidence_page.text
