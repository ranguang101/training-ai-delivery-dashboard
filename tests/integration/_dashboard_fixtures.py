"""Shared fixtures for standalone-dashboard hardening tests (not collected)."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_panel_root(
    root: Path,
    *,
    project_status: dict | None = None,
    with_templates: bool = False,
) -> Path:
    """Build a minimal standalone-panel project root at the given path."""
    (root / "app" / "static").mkdir(parents=True)
    (root / "app" / "templates").mkdir(parents=True)
    if with_templates:
        shutil.copytree(
            PROJECT_ROOT / "app" / "templates",
            root / "app" / "templates",
            dirs_exist_ok=True,
        )
    if project_status is not None:
        (root / "project-status.json").write_text(
            json.dumps(project_status, ensure_ascii=False), encoding="utf-8"
        )
    return root


def minimal_project_status(
    *,
    project_name: str = "测试项目",
    last_updated: str = "2026-08-20T00:00:00+08:00",
    delivery_lines: list | None = None,
    stages: list | None = None,
) -> dict:
    project: dict = {
        "project_name": project_name,
        "last_updated": last_updated,
        "current_work": {
            "title": "面板硬化",
            "detail": "安全修复与降级。",
            "next_checkpoint": "回归通过",
        },
        "completed_capabilities": ["交付追踪"],
        "attention_items": [],
        "recent_updates": [
            {
                "date": "2026-08-20",
                "title": "面板硬化",
                "detail": "安全修复与降级。",
            }
        ],
    }
    if delivery_lines is not None:
        project["delivery_lines"] = delivery_lines
    if stages is not None:
        project["stages"] = stages
    return project


def delivery_line_fixture(
    evidence_level: str,
    *,
    ordinal: int = 1,
    delivery_status: str = "integration",
    contract_status: str | None = None,
    candidate_status: str | None = None,
    runtime_status: str | None = None,
    open_blockers: list[dict] | None = None,
) -> dict:
    """Build a synthetic top-level delivery line for D-level relation tests."""
    rank = (
        int(evidence_level[1:])
        if len(evidence_level) == 2 and evidence_level[1].isdigit()
        else 0
    )
    contract_status = contract_status or ("frozen" if rank >= 3 else "not_frozen")
    candidate_status = candidate_status or ("fixed" if rank >= 3 else "not_fixed")
    runtime_status = runtime_status or (
        "passed" if rank >= 6 else "evidence_ready" if rank >= 5 else "open"
    )
    evidence_links = []
    if rank:
        evidence_links.append(
            {
                "id": f"FIXTURE-EVIDENCE-{ordinal}-BASE",
                "kind": "document",
                "evidence_level": evidence_level,
                "status": "confirmed",
                "source_role": "product",
                "safe_summary": f"Synthetic evidence {ordinal}",
            }
        )
    if rank >= 5:
        evidence_links.append(
            {
                "id": f"FIXTURE-EVIDENCE-{ordinal}-TEST",
                "kind": "test_run",
                "evidence_level": "D5",
                "status": "passed",
                "source_role": "testing",
                "safe_summary": f"Synthetic test evidence {ordinal}",
            }
        )
    if rank >= 6:
        evidence_links.append(
            {
                "id": f"FIXTURE-EVIDENCE-{ordinal}-CONFIRM",
                "kind": "handoff",
                "evidence_level": "D6",
                "status": "confirmed",
                "source_role": "project_owner",
                "safe_summary": f"Synthetic confirmation {ordinal}",
            }
        )
    return {
        "id": f"fixture-line-{ordinal}",
        "delivery_track": f"fixture-track-{ordinal}",
        "name": f"Synthetic delivery line {ordinal}",
        "summary": f"Synthetic line summary {ordinal}",
        "delivery_status": delivery_status,
        "evidence_level": evidence_level,
        "verified_at": r3_time(),
        "updated_at": r3_time(),
        "source_role": "development",
        "contract_state": {"status": contract_status, "safe_summary": "Synthetic contract"},
        "candidate_version": {"status": candidate_status, "safe_summary": "Synthetic candidate"},
        "runtime_gate": {"status": runtime_status, "safe_summary": "Synthetic runtime"},
        "scope_in": [],
        "scope_out": [],
        "evidence_links": evidence_links,
        "open_blockers": open_blockers or [],
    }


def quality_workspace_fixture(
    *,
    case_statuses: tuple[str, ...] = ("passed", "failed", "blocked", "not_executed"),
    automation_kinds: tuple[str, ...] = ("automated", "manual", "manual", "automated"),
    defect_statuses: tuple[str, ...] = ("in_progress", "ready_for_retest", "closed"),
) -> dict:
    """Build synthetic quality records without copying a real project instance."""
    cases = []
    executions = []
    for index, case_status in enumerate(case_statuses, 1):
        case_id = f"FIXTURE-CASE-{index}"
        cases.append(
            {
                "case_id": case_id,
                "quality_requirement_id": "FIXTURE-QUALITY-1",
                "case_status": case_status,
                "automation_kind": automation_kinds[index - 1],
            }
        )
        if case_status != "not_executed":
            executions.append(
                {
                    "case_id": case_id,
                    "run_id": f"FIXTURE-RUN-{index}",
                    "execution_status": case_status,
                    "executed_at": r3_time(),
                    "candidate_ref": "FIXTURE-CANDIDATE-1",
                }
            )
    return {
        "requirements": [
            {
                "quality_requirement_id": "FIXTURE-QUALITY-1",
                "status": "executing",
                "candidate_status": "fixed",
            }
        ],
        "formal_cases": cases,
        "case_executions": executions,
        "automation_runs": [],
        "defects": [
            {
                "defect_id": f"FIXTURE-DEFECT-{index}",
                "status": status,
                "severity": "medium",
            }
            for index, status in enumerate(defect_statuses, 1)
        ],
        "final_reports": [],
    }


def state_driven_project_status(*delivery_lines: dict, quality: dict | None = None) -> dict:
    """Minimal shared source for lightweight API and browser fixture tests."""
    project = minimal_project_status(
        project_name="Synthetic dashboard project",
        last_updated=r3_time(),
        delivery_lines=list(delivery_lines),
    )
    project.update(
        {
            "overall_status": "in_progress",
            "roles": {
                role: {
                    "name": f"Synthetic {role}",
                    "status": "in_progress",
                    "current": "Synthetic current work",
                    "next": "Synthetic next action",
                    "waiting_for": "Synthetic dependency",
                }
                for role in ("frontend", "development", "testing")
            },
        }
    )
    if quality is not None:
        project["quality_workspace_r4"] = quality
    return project


def write_valid_run(
    root: Path,
    run_id: str = "RUN-P1-20260809-000001",
    *,
    counts: dict | None = None,
    git_dirty: bool = False,
    case_results: list | None = None,
    started_at: str = "2026-08-09T00:00:00+08:00",
) -> Path:
    run_dir = root / "reports" / "test-runs" / run_id
    run_dir.mkdir(parents=True)
    summary = {
        "id": run_id,
        "stage": "P1",
        "started_at": started_at,
        "code_version": "1c950ced792a3d8d2cb95fc6993fd8b05d3fb931",
        "git_dirty": git_dirty,
        "counts": counts
        or {
            "executed": 3,
            "passed": 3,
            "failed": 0,
            "blocked": 0,
            "not_executed": 0,
        },
        "case_results": case_results
        or [
            {"case_id": "P1-TC-001", "status": "passed"},
            {"case_id": "P1-TC-002", "status": "passed"},
            {"case_id": "P1-TC-003", "status": "passed"},
        ],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False), encoding="utf-8"
    )
    return run_dir


_BEIJING = timezone(timedelta(hours=8))


def r3_time(hours_ago: float = 0.0) -> str:
    """Return a tz-aware ISO 8601 timestamp, optionally in the past."""
    moment = datetime.now(UTC) - timedelta(hours=hours_ago)
    return moment.astimezone(_BEIJING).isoformat(timespec="seconds")


def r3_line(
    delivery_line_id: str = "mvp-a-management-foundation",
    *,
    name: str = "MVP-A 管理运营底座",
    delivery_status: str = "implementation",
    verified_at: str | None = None,
    can_enter_product_acceptance: bool = False,
    can_enter_controlled_trial: bool = False,
    **overrides: object,
) -> dict:
    line: dict = {
        "delivery_line_id": delivery_line_id,
        "name": name,
        "scope_summary": "受控范围摘要",
        "delivery_status": delivery_status,
        "current_conclusion": "开发验证完成，尚未进入独立测试",
        "current_candidate_summary": "候选待固定",
        "next_gate_summary": "下一步：独立测试准入门禁",
        "can_enter_product_acceptance": can_enter_product_acceptance,
        "can_enter_controlled_trial": can_enter_controlled_trial,
        "verified_at": verified_at or r3_time(),
    }
    line.update(overrides)
    return line


def r3_fact(
    fact_id: str,
    delivery_line_id: str = "mvp-a-management-foundation",
    fact_type: str = "completed",
    *,
    status: str = "verified",
    owner_role: str = "development",
    verified_at: str | None = None,
    summary: str = "安全事实摘要",
    evidence_refs: list | None = None,
    workspace_ids: list | None = None,
    candidate: dict | None = None,
) -> dict:
    fact: dict = {
        "fact_id": fact_id,
        "delivery_line_id": delivery_line_id,
        "fact_type": fact_type,
        "status": status,
        "owner_role": owner_role,
        "verified_at": verified_at or r3_time(),
        "summary": summary,
        "evidence_refs": evidence_refs if evidence_refs is not None else [],
        "workspace_ids": workspace_ids
        if workspace_ids is not None
        else ["collaboration", "development"],
    }
    if candidate is not None:
        fact.update(candidate)
    return fact


def r3_candidate(
    *,
    backend: str = "b1",
    frontend: str = "f1",
    migration: str = "不适用",
    handoff: str = "HO-1",
    candidate_status: str = "pending",
) -> dict:
    return {
        "backend_candidate": backend,
        "frontend_candidate": frontend,
        "migration_summary": migration,
        "startup_handoff_ref": handoff,
        "candidate_status": candidate_status,
    }


def r3_target(
    evidence_type: str = "document",
    evidence_id: str = "DOC-1",
    *,
    status: str = "valid",
    purpose: str = "reference",
    owner_role: str = "development",
    verified_at: str | None = None,
    title: str = "安全文档",
    safe_summary: str = "安全摘要",
    related_evidence_ids: list | None = None,
) -> dict:
    return {
        "type": evidence_type,
        "id": evidence_id,
        "title": title,
        "status": status,
        "purpose": purpose,
        "owner_role": owner_role,
        "verified_at": verified_at or r3_time(),
        "safe_summary": safe_summary,
        "related_evidence_ids": related_evidence_ids or [],
    }


def r3_combo(
    delivery_line_id: str,
    *,
    backend: str = "b1",
    frontend: str = "f1",
    migration: str = "不适用",
    handoff: str = "HO-1",
) -> dict:
    return {
        "delivery_line_id": delivery_line_id,
        "backend_candidate": backend,
        "frontend_candidate": frontend,
        "migration_summary": migration,
        "startup_handoff_ref": handoff,
    }


def r3_test_run_target(
    root: Path,
    run_id: str = "RUN-P1-20260809-000001",
    *,
    verified_at: str | None = None,
    title: str = "受控测试运行",
    safe_summary: str = "运行摘要",
    **overrides: object,
) -> dict:
    """写真实受控运行资产并返回对应 evidence_target（test_run 类）。"""
    write_valid_run(root, run_id=run_id)
    target = r3_target(
        "test_run",
        run_id,
        purpose="independent_test",
        verified_at=verified_at,
        title=title,
        safe_summary=safe_summary,
    )
    target.update(overrides)
    return target


def r3_report_run_target(
    root: Path,
    run_id: str = "RUN-MVP-A-20260812-001000",
    *,
    verified_at: str | None = None,
    title: str = "独立测试报告",
    safe_summary: str = "报告摘要",
    **overrides: object,
) -> dict:
    """写独立测试报告类运行资产（无 summary.json）并返回 evidence_target。"""
    run_dir = root / "reports" / "test-runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "independent-test-report.md").write_text(
        f"# 独立测试报告\n\n运行编号 {run_id}\n", encoding="utf-8"
    )
    target = r3_target(
        "test_run",
        run_id,
        purpose="independent_test",
        verified_at=verified_at,
        title=title,
        safe_summary=safe_summary,
    )
    target.update(overrides)
    return target


def r3_handoff_target(
    root: Path,
    handoff_id: str = "HO-ACCEPT-1",
    *,
    verified_at: str | None = None,
    title: str = "受控交接记录",
    safe_summary: str = "交接摘要",
    **overrides: object,
) -> dict:
    """写真实交接记录资产并返回对应 evidence_target（handoff 类）。"""
    handoffs_dir = root / "docs" / "internal" / "handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    (handoffs_dir / f"handoff-{handoff_id.lower()}.md").write_text(
        f"# 交接记录\n\n交接编号 {handoff_id}\n", encoding="utf-8"
    )
    target = r3_target(
        "handoff",
        handoff_id,
        purpose="reference",
        verified_at=verified_at,
        title=title,
        safe_summary=safe_summary,
    )
    target.update(overrides)
    return target


def r3_project_status(*, dashboard_r3: dict) -> dict:
    project = minimal_project_status()
    project["dashboard_r3"] = dashboard_r3
    return project


def make_r3_root(
    root: Path,
    *,
    dashboard_r3: dict | None = None,
    with_templates: bool = False,
) -> Path:
    """Build a standalone panel root whose project-status.json carries dashboard_r3."""
    return make_panel_root(
        root,
        project_status=r3_project_status(dashboard_r3=dashboard_r3 or {}),
        with_templates=with_templates,
    )


