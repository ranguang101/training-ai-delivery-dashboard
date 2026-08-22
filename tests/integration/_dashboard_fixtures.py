"""Shared fixtures for standalone-dashboard hardening tests (not collected)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_panel_root(
    root: Path,
    *,
    project_status: dict | None = None,
    with_templates: bool = False,
    template_marker: str | None = None,
    static_marker: str | None = None,
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
    if template_marker is not None:
        overview = root / "app" / "templates" / "project_status.html"
        overview.write_text(
            overview.read_text(encoding="utf-8") + f"\n<!-- {template_marker} -->\n",
            encoding="utf-8",
        )
    if static_marker is not None:
        (root / "app" / "static" / static_marker).write_text(
            f"marker:{static_marker}", encoding="utf-8"
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
