"""R3 独立交付看板的只读、安全路由。

本仓库不再承载旧项目内嵌看板的文档、缺陷、报告或阶段详情页；浏览器只可
访问同步摘要、四工作区 R3 投影及受控证据详情。
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import PROJECT_ROOT, get_settings
from app.services.delivery_detail import (
    DeliveryDetailNotFound,
    build_delivery_line_detail,
    build_delivery_line_evidence_detail,
)
from app.services.delivery_monitor import (
    R3_TEST_FIXTURE_VALUES,
    WORKSPACE_ID_VALUES,
    build_r3_workspace_view,
    load_r3_evidence_detail,
)
from app.services.lightweight_dashboard import PAGE_LABELS, build_lightweight_dashboard
from app.services.project_status_cache import load_project_status, project_status_revision
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
        snapshot = load_project_status(project_root)
        payload = snapshot.payload
        revision = snapshot.revision
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
        revision = project_status_revision(project_root)
    if not isinstance(payload, dict):
        payload = {}
    project_name = payload.get("project_name")
    last_updated = payload.get("last_updated")
    return {
        "project_name": project_name if isinstance(project_name, str) else None,
        "last_updated": last_updated if isinstance(last_updated, str) else None,
        "revision": revision,
    }


def _render_workspace(request: Request, workspace_id: str) -> HTMLResponse:
    sync = _sync_projection(_project_root(request))
    return _templates_for(request).TemplateResponse(
        request,
        "safe_workspace_overview.html"
        if workspace_id == "collaboration"
        else "safe_workspace_detail.html",
        {
            "workspace_id": workspace_id,
            "workspace_label": WORKSPACE_LABELS[workspace_id],
            "initial_revision": sync["revision"],
        },
    )


def _render_lightweight_page(
    request: Request, page: str, *, line_id: str | None = None
) -> HTMLResponse:
    line_id = line_id or None
    try:
        sync = _sync_projection(_project_root(request))
        selected_line = None
        if line_id is not None:
            selected_line = build_lightweight_dashboard(
                page=page, line_id=line_id, project_root=_project_root(request)
            ).get("selected_line")
            if selected_line is None:
                raise KeyError(line_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="DASHBOARD_LINE_NOT_FOUND") from exc
    template_name = (
        "safe_dashboard_v2.html" if page == "dashboard_v2" else "safe_dashboard_page.html"
    )
    return _templates_for(request).TemplateResponse(
        request,
        template_name,
        {
            "page": page,
            "page_label": PAGE_LABELS.get(page, "项目交付看板"),
            "line_id": line_id or "",
            "initial_revision": sync["revision"],
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
    "/api/v1/project-status/delivery-lines/{delivery_line_id}/detail",
    include_in_schema=False,
)
def delivery_line_detail_data(delivery_line_id: str, request: Request) -> dict:
    """L2 generic delivery-line detail; all relations are server-side scoped."""
    _ensure_enabled()
    try:
        data = build_delivery_line_detail(
            delivery_line_id, project_root=_project_root(request)
        )
    except (DeliveryDetailNotFound, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="DELIVERY_LINE_DETAIL_NOT_FOUND") from exc
    return {"success": True, "data": data}


@router.get(
    "/api/v1/project-status/delivery-lines/{delivery_line_id}/evidence/{evidence_type}/{evidence_id}",
    include_in_schema=False,
)
def delivery_line_evidence_data(
    delivery_line_id: str, evidence_type: str, evidence_id: str, request: Request
) -> dict:
    """L4 controlled evidence projection; raw evidence remains unavailable."""
    _ensure_enabled()
    try:
        data = build_delivery_line_evidence_detail(
            delivery_line_id,
            evidence_type,
            evidence_id,
            project_root=_project_root(request),
        )
    except (DeliveryDetailNotFound, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="DELIVERY_EVIDENCE_NOT_FOUND") from exc
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
    sync = _sync_projection(_project_root(request))
    return _templates_for(request).TemplateResponse(
        request,
        "safe_quality_requirements.html",
        {
            "quality_requirement_id": requirement_id,
            "initial_revision": sync["revision"],
        },
    )


@router.get(
    "/project-status/tests",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def testing_dashboard_page(request: Request, line: str | None = None) -> HTMLResponse:
    """Lightweight quality/testing page; the R4 detail remains under /requirements."""
    _ensure_enabled()
    return _render_lightweight_page(request, "testing", line_id=line)


@router.get(
    "/project-status/tests/requirements",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def quality_requirements_page(request: Request) -> HTMLResponse:
    """R4 quality workspace entry; it only loads the controlled lifecycle API."""
    _ensure_enabled()
    return _render_quality_requirements(request)


@router.get("/api/v1/project-status/lightweight", include_in_schema=False)
def lightweight_dashboard_data(
    request: Request, page: str = "overview", line: str | None = None
) -> dict:
    _ensure_enabled()
    line = line or None
    try:
        data = build_lightweight_dashboard(
            page=page, line_id=line, project_root=_project_root(request)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="DASHBOARD_PAGE_NOT_FOUND") from exc
    return {"success": True, "data": data}


@router.get(
    "/project-status/delivery-lines/{delivery_line_id}/evidence/{evidence_type}/{evidence_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def delivery_line_evidence_page(
    delivery_line_id: str, evidence_type: str, evidence_id: str, request: Request
) -> HTMLResponse:
    _ensure_enabled()
    try:
        detail = build_delivery_line_evidence_detail(
            delivery_line_id,
            evidence_type,
            evidence_id,
            project_root=_project_root(request),
        )
    except (DeliveryDetailNotFound, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="DELIVERY_EVIDENCE_NOT_FOUND") from exc
    return _templates_for(request).TemplateResponse(
        request,
        "safe_delivery_evidence.html",
        {
            "detail": detail,
            "delivery_line_id": delivery_line_id,
            "return_href": f"/project-status/delivery-lines/{delivery_line_id}",
        },
    )


@router.get(
    "/project-status/delivery-lines/{delivery_line_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def delivery_line_detail_page(delivery_line_id: str, request: Request) -> HTMLResponse:
    _ensure_enabled()
    try:
        build_delivery_line_detail(delivery_line_id, project_root=_project_root(request))
    except (DeliveryDetailNotFound, TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="DELIVERY_LINE_DETAIL_NOT_FOUND") from exc
    sync = _sync_projection(_project_root(request))
    return _templates_for(request).TemplateResponse(
        request,
        "safe_delivery_line_detail.html",
        {
            "delivery_line_id": delivery_line_id,
            "initial_revision": sync["revision"],
        },
    )


@router.get(
    "/project-status/tests/requirements/{quality_requirement_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def quality_requirement_detail_page(quality_requirement_id: str, request: Request) -> HTMLResponse:
    _ensure_enabled()
    return _render_quality_requirements(request, requirement_id=quality_requirement_id)


@router.get("/project-status", response_class=HTMLResponse, include_in_schema=False)
def project_status_page(request: Request, line: str | None = None) -> HTMLResponse:
    """Lightweight five-page dashboard overview; R3 remains under /workspaces."""
    _ensure_enabled()
    return _render_lightweight_page(request, "overview", line_id=line)


@router.get("/project-status/product", response_class=HTMLResponse, include_in_schema=False)
def product_dashboard_page(request: Request, line: str | None = None) -> HTMLResponse:
    _ensure_enabled()
    return _render_lightweight_page(request, "product", line_id=line)


@router.get("/project-status/frontend", response_class=HTMLResponse, include_in_schema=False)
def frontend_dashboard_page(request: Request, line: str | None = None) -> HTMLResponse:
    _ensure_enabled()
    return _render_lightweight_page(request, "frontend", line_id=line)


@router.get("/project-status/development", response_class=HTMLResponse, include_in_schema=False)
def development_dashboard_page(request: Request, line: str | None = None) -> HTMLResponse:
    _ensure_enabled()
    return _render_lightweight_page(request, "development", line_id=line)


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


@router.get(
    "/project-status/v2",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def fusion_dashboard_v2_page(request: Request) -> HTMLResponse:
    """PRD v2.0 Plane executive + MeterSphere tree-table fusion dashboard."""
    _ensure_enabled()
    return _render_lightweight_page(request, "dashboard_v2")
