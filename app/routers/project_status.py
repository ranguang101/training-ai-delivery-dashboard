"""R3 独立交付看板的只读、安全路由。

本仓库不再承载旧项目内嵌看板的文档、缺陷、报告或阶段详情页；浏览器只可
访问同步摘要、四工作区 R3 投影及受控证据详情。
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import PROJECT_ROOT, get_settings
from app.services.delivery_monitor import (
    R3_TEST_FIXTURE_VALUES,
    WORKSPACE_ID_VALUES,
    build_r3_workspace_view,
    load_r3_evidence_detail,
)
from app.services.quality_lifecycle import (
    QualityLifecycleNotFound,
    build_quality_requirement_detail,
    build_quality_requirement_overview,
)

router = APIRouter(tags=["project-status"])
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))

WORKSPACE_LABELS = {
    "collaboration": "协作总览",
    "development": "服务端工作区",
    "frontend": "前端工作区",
    "testing": "质量工作区",
}


def _ensure_enabled() -> None:
    if not get_settings().project_status_enabled:
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_DISABLED")


def _project_root(request: Request) -> Path:
    root = getattr(request.app.state, "dashboard_project_root", None)
    return Path(root).resolve() if root is not None else PROJECT_ROOT


def _templates_for(request: Request) -> Jinja2Templates:
    configured = getattr(request.app.state, "project_status_templates", None)
    return configured if configured is not None else templates


def _r3_test_fixture(request: Request) -> str | None:
    """Read the runner-owned UI scenario selector; it is never request controlled."""
    fixture = getattr(request.app.state, "dashboard_r3_test_fixture", None)
    return fixture if fixture in R3_TEST_FIXTURE_VALUES else None


def _sync_projection(project_root: Path) -> dict[str, str | None]:
    """The polling endpoint deliberately exposes only the display-safe clock."""
    try:
        source = (project_root / "project-status.json").read_text(encoding="utf-8")
        payload = json.loads(source)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    project_name = payload.get("project_name")
    last_updated = payload.get("last_updated")
    return {
        "project_name": project_name if isinstance(project_name, str) else None,
        "last_updated": last_updated if isinstance(last_updated, str) else None,
    }


def _render_workspace(request: Request, workspace_id: str) -> HTMLResponse:
    return _templates_for(request).TemplateResponse(
        request,
        "safe_workspace_overview.html"
        if workspace_id == "collaboration"
        else "safe_workspace_detail.html",
        {
            "workspace_id": workspace_id,
            "workspace_label": WORKSPACE_LABELS[workspace_id],
        },
    )


@router.get("/api/v1/project-status", include_in_schema=False)
def sync_project_status(request: Request) -> dict:
    _ensure_enabled()
    return {"success": True, "data": _sync_projection(_project_root(request))}


@router.get(
    "/api/v1/project-status/dashboard/r3/workspaces/{workspace_id}",
    include_in_schema=False,
)
def r3_workspace_data(workspace_id: str, request: Request, line: str | None = None) -> dict:
    _ensure_enabled()
    if workspace_id not in WORKSPACE_ID_VALUES:
        raise HTTPException(status_code=404, detail="R3_WORKSPACE_NOT_FOUND")
    if getattr(request.app.state, "dashboard_test_fault", None) == "r3-workspace-503":
        raise HTTPException(status_code=503, detail="R3_TEST_WORKSPACE_UNAVAILABLE")
    try:
        data = build_r3_workspace_view(
            workspace_id,
            line_id=line,
            project_root=_project_root(request),
            test_fixture=_r3_test_fixture(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="R3_LINE_NOT_FOUND") from exc
    return {"success": True, "data": data}


@router.get(
    "/api/v1/project-status/dashboard/r3/evidence/{evidence_type}/{evidence_id}",
    include_in_schema=False,
)
def r3_evidence_data(evidence_type: str, evidence_id: str, request: Request) -> dict:
    _ensure_enabled()
    try:
        data = load_r3_evidence_detail(
            evidence_type, evidence_id, project_root=_project_root(request)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="R3_EVIDENCE_NOT_FOUND") from exc
    return {"success": True, "data": data}


@router.get(
    "/api/v1/project-status/quality-requirements",
    include_in_schema=False,
)
def quality_requirement_overview(
    request: Request, requirement: str | None = None, line: str | None = None
) -> dict:
    """R4 quality lifecycle overview: only registered, safe structured fields."""
    _ensure_enabled()
    try:
        data = build_quality_requirement_overview(
            project_root=_project_root(request),
            requirement_id=requirement,
            line_id=line,
        )
    except QualityLifecycleNotFound as exc:
        raise HTTPException(status_code=404, detail="QUALITY_REQUIREMENT_NOT_FOUND") from exc
    return {"success": True, "data": data}


@router.get(
    "/api/v1/project-status/quality-requirements/{quality_requirement_id}",
    include_in_schema=False,
)
def quality_requirement_detail(
    quality_requirement_id: str, request: Request, line: str | None = None
) -> dict:
    """R4 safe detail projection; raw reports, logs and paths stay unavailable."""
    _ensure_enabled()
    try:
        data = build_quality_requirement_detail(
            quality_requirement_id,
            project_root=_project_root(request),
            line_id=line,
        )
    except QualityLifecycleNotFound as exc:
        raise HTTPException(status_code=404, detail="QUALITY_REQUIREMENT_NOT_FOUND") from exc
    return {"success": True, "data": data}


def _render_quality_requirements(
    request: Request, *, requirement_id: str | None = None
) -> HTMLResponse:
    return _templates_for(request).TemplateResponse(
        request,
        "safe_quality_requirements.html",
        {"quality_requirement_id": requirement_id},
    )


@router.get(
    "/project-status/tests",
    response_class=HTMLResponse,
    include_in_schema=False,
)
@router.get(
    "/project-status/tests/requirements",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def quality_requirements_page(request: Request) -> HTMLResponse:
    """R4 quality workspace entry; it only loads the controlled lifecycle API."""
    _ensure_enabled()
    return _render_quality_requirements(request)


@router.get(
    "/project-status/tests/requirements/{quality_requirement_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def quality_requirement_detail_page(quality_requirement_id: str, request: Request) -> HTMLResponse:
    _ensure_enabled()
    return _render_quality_requirements(request, requirement_id=quality_requirement_id)


@router.get("/project-status", response_class=HTMLResponse, include_in_schema=False)
def project_status_page(request: Request, line: str | None = None) -> RedirectResponse:
    """R3 has one safe collaboration overview; retain the historical entry URL."""
    _ensure_enabled()
    query = f"?{urlencode({'line': line})}" if line else ""
    return RedirectResponse(url=f"/project-status/workspaces{query}", status_code=307)


@router.get(
    "/project-status/workspaces",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def workspace_overview_page(request: Request) -> HTMLResponse:
    _ensure_enabled()
    return _render_workspace(request, "collaboration")


@router.get(
    "/project-status/workspaces/{workspace_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def workspace_detail_page(workspace_id: str, request: Request) -> HTMLResponse:
    _ensure_enabled()
    if workspace_id not in WORKSPACE_LABELS or workspace_id == "collaboration":
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_WORKSPACE_NOT_FOUND")
    return _render_workspace(request, workspace_id)
