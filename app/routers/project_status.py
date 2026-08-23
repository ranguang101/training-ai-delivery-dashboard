import json
import posixpath
import re
from html import escape as html_escape
from html import unescape as html_unescape
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import PROJECT_ROOT, get_settings
from app.services.delivery_monitor import (
    WORKSPACE_ID_VALUES,
    build_r3_workspace_view,
    load_r3_evidence_detail,
)
from app.services.document_catalog import (
    STATUS_LABELS as DOCUMENT_STATUS_LABELS,
)
from app.services.document_catalog import (
    build_document_catalog,
    load_document,
    render_document,
)
from app.services.project_status import (
    build_delivery_dashboard_view,
    build_workspace_dashboard_view,
    load_delivery_evidence_view,
    load_project_status,
    load_stage,
    render_stage_requirements,
)
from app.services.test_management import (
    build_case_design_center,
    build_test_automation_center,
    build_test_center,
    cases_with_latest_result,
    load_case_design_task,
    load_defect,
    load_defects,
    load_test_automation_evidence,
    load_test_automation_run,
    load_test_integrations,
    load_test_run,
    load_test_runs,
    stage_test_summary,
    summarize_run_case_types,
)

router = APIRouter(tags=["project-status"])
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))

STATUS_LABELS = {
    "pending": "未开始",
    "in_progress": "进行中",
    "ready": "待验收",
    "accepted": "已完成",
    "paused": "已暂停",
    "blocked": "有阻塞",
}

TEST_STATUS_LABELS = {
    "not_started": "未开始",
    "designing": "编写中",
    "ready": "待执行",
    "in_progress": "执行中",
    "passed": "已通过",
    "failed": "有失败",
    "blocked": "有阻塞",
}

TECHNICAL_REVIEW_STATUS_LABELS = {
    "structure_ready": "体系已就绪",
    "assessed": "已完成参考评估",
    "draft": "草稿",
    "pending_review": "待评审",
    "approved": "已确认",
    "in_implementation": "开发执行中",
    "implemented": "已实施",
    "superseded": "已被替代",
    "pending": "待开始",
}

ROLE_STATUS_LABELS = {
    "handoff_ready": "待交接",
    "in_progress": "进行中",
    "waiting": "等待输入",
    "blocked": "有阻塞",
    "completed": "已完成",
}

HANDOFF_STATUS_LABELS = {
    "draft": "草稿",
    "ready": "待接收",
    "received": "已接收",
    "in_progress": "处理中",
    "completed": "已完成",
    "returned": "已退回",
}

CASE_TYPE_LABELS = {
    "unit": "单元",
    "api": "接口",
    "integration": "集成",
    "ui": "UI",
    "regression": "回归",
    "architecture": "架构",
    "security": "安全",
    "manual": "人工",
}

AUTOMATION_STATUS_LABELS = {
    "automated": "已自动化",
    "planned": "计划自动化",
    "manual": "人工检查",
}

RESULT_STATUS_LABELS = {
    "passed": "通过",
    "failed": "失败",
    "blocked": "阻塞",
    "not_executed": "未执行",
    "manual_pending": "待人工",
    "automation_pending": "待自动化",
    "deferred": "阶段后置",
}

INTEGRATION_STATUS_LABELS = {
    "connected": "已接入",
    "planned": "待接入",
    "blocked": "有阻塞",
}

DEFECT_STATUS_LABELS = {
    "open": "新发现",
    "confirmed": "已确认",
    "fixing": "修复中",
    "fixed": "已修复待复测",
    "retest_passed": "复测通过",
    "reopened": "重新打开",
    "closed": "已关闭",
}

SEVERITY_LABELS = {"critical": "严重", "high": "高", "medium": "中", "low": "低"}

# The dashboard may be rendered before its read-only API has loaded.  Keep the
# server-rendered fallback as understandable as the JavaScript-enhanced view;
# raw storage values are not useful status text for a project owner.
DELIVERY_STATE_LABELS = {
    "planning": "规划中",
    "contract_freeze": "契约待冻结",
    "implementation": "实施中",
    "integration": "联调中",
    "independent_test": "独立测试中",
    "product_acceptance": "产品验收中",
    "ready_for_trial": "可试用",
    "not_frozen": "待冻结",
    "frozen": "已冻结",
    "retest_required": "待复验",
    "not_applicable": "不适用",
    "not_fixed": "待固定",
    "fixed": "已固定",
    "superseded": "已替换",
    "not_assessed": "待评估",
    "evidence_ready": "证据已齐",
    "open": "未解除",
    "passed": "已通过",
    "blocked": "有阻塞",
}

SAFE_WORKSPACE_PAGE_LABELS = {
    "collaboration": "协作总览",
    "development": "服务端工作区",
    "frontend": "前端工作区",
    "testing": "质量工作区",
}

PROJECT_STATUS_LOAD_ERRORS = (ValueError, OSError, json.JSONDecodeError, UnicodeDecodeError)

_ANCHOR_PATTERN = re.compile(r'<a\s+href="([^"]*)"\s*>(.*?)</a>', re.DOTALL)


def _resolve_document_link(
    href: str, document: dict, documents_by_relative_path: dict[str, str]
) -> tuple[str, str | None]:
    """Classify one link target: (keep|canonical|neutralize, new_href)."""
    value = html_unescape(href).strip()
    if not value:
        return "neutralize", None
    fragment = ""
    if "#" in value:
        value, fragment = value.split("#", 1)
    lowered = value.lower()
    if lowered.startswith(("file:", "javascript:", "vbscript:", "data:")):
        return "neutralize", None
    if (
        not lowered.endswith(".md")
        or lowered.startswith(("http:", "https:", "mailto:", "/", "#"))
        or "://" in value
    ):
        return "keep", None
    document_dir = posixpath.dirname(document["relative_path"])
    resolved = posixpath.normpath(
        posixpath.join(document_dir, value) if document_dir else value
    )
    if resolved.startswith("../") or resolved == "..":
        return "neutralize", None
    document_id = documents_by_relative_path.get(resolved)
    if document_id is None:
        return "neutralize", None
    suffix = f"#{html_escape(fragment, quote=True)}" if fragment else ""
    return "canonical", f"/project-status/documents/{document_id}{suffix}"


def rewrite_document_links(
    rendered_html: str, document: dict, documents: list[dict]
) -> str:
    """Rewrite in-project Markdown links to canonical document URLs.

    Applied on the sanitized render: raw relative ``requirements/...md`` links
    become ``/project-status/documents/{id}``, and stale targets degrade to
    plain text so readers never land on filesystem-relative paths.
    """
    documents_by_relative_path = {item["relative_path"]: item["id"] for item in documents}

    def replacement(match: re.Match[str]) -> str:
        href, inner = match.group(1), match.group(2)
        action, value = _resolve_document_link(href, document, documents_by_relative_path)
        if action == "keep":
            return match.group(0)
        if action == "neutralize":
            return (
                f'<span class="doc-link-missing" title="目标文档已迁移或已删除">'
                f"{inner}</span>"
            )
        return f'<a href="{html_escape(value, quote=True)}">{inner}</a>'

    return _ANCHOR_PATTERN.sub(replacement, rendered_html)


def ensure_project_status_enabled() -> None:
    if not get_settings().project_status_enabled:
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_DISABLED")


def _raise_delivery_dashboard_test_fault(request: Request) -> None:
    """Inject a management-panel-only fault for independent UI verification."""
    if getattr(request.app.state, "dashboard_test_fault", None) == "dashboard_404":
        raise HTTPException(status_code=404, detail="DASHBOARD_TEST_NOT_FOUND")


def _request_project_root(request: Request) -> Path | None:
    """Resolve the per-request project root set by the standalone panel."""
    root = getattr(request.app.state, "dashboard_project_root", None)
    return Path(root).resolve() if root is not None else None


def _is_standalone_panel(request: Request) -> bool:
    return getattr(request.app.state, "dashboard_mode", None) == "read_only_local"


def _panel_route_closed(request: Request) -> None:
    """Raw detail pages and raw data APIs are not panel data entries."""
    if _is_standalone_panel(request):
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_ROUTE_CLOSED_IN_PANEL")


def _templates_for(request: Request) -> Jinja2Templates:
    configured = getattr(request.app.state, "project_status_templates", None)
    return configured if configured is not None else templates


def _load_project_status_for(request: Request) -> dict:
    """Load project status honoring the panel root, keeping business defaults."""
    root = _request_project_root(request)
    if root is None:
        return load_project_status()
    return load_project_status(project_root=root)


def _render_degraded_project_status(request: Request):
    """Safe degraded page when project-status.json cannot be validated."""
    return _templates_for(request).TemplateResponse(
        request,
        "project_status_degraded.html",
        {"degraded": True},
        status_code=200,
    )


def _render_safe_workspace_page(request: Request, workspace_id: str):
    """Render a panel-only workspace shell without loading raw status content."""
    return _templates_for(request).TemplateResponse(
        request,
        "safe_workspace_overview.html"
        if workspace_id == "collaboration"
        else "safe_workspace_detail.html",
        {
            "workspace_id": workspace_id,
            "workspace_label": SAFE_WORKSPACE_PAGE_LABELS[workspace_id],
        },
    )


def _resolve_workspace_document_groups(
    workspace: dict[str, object], *, project_root: Path | None = None
) -> list[dict[str, object]]:
    """Resolve configured workspace links against the canonical document catalog."""
    documents_by_path = {
        document["relative_path"]: document
        for document in build_document_catalog(project_root)["documents"]
    }
    groups: list[dict[str, object]] = []

    for configured_group in workspace.get("document_workspace", []):
        group = dict(configured_group)
        paths = group.pop("paths", [])
        group["documents"] = [
            documents_by_path[path] for path in paths if path in documents_by_path
        ]
        group["missing_paths"] = [
            path for path in paths if path not in documents_by_path
        ]
        groups.append(group)

    return groups


@router.get("/api/v1/project-status", include_in_schema=False)
def project_status_data(request: Request) -> dict:
    ensure_project_status_enabled()
    if _is_standalone_panel(request):
        # The standalone panel may only poll the sync clock, never raw fields.
        try:
            project = _load_project_status_for(request)
        except PROJECT_STATUS_LOAD_ERRORS:
            project = {}
        return {
            "success": True,
            "data": {
                "project_name": project.get("project_name"),
                "last_updated": project.get("last_updated"),
            },
        }
    return {"success": True, "data": load_project_status()}


@router.get("/api/v1/project-status/dashboard", include_in_schema=False)
def project_delivery_dashboard_data(request: Request) -> dict:
    """Return the safe delivery-tracking projection for the management dashboard.

    This endpoint intentionally excludes raw test-run environments, defect
    reproduction details, source document paths, and all business data.
    """
    ensure_project_status_enabled()
    _raise_delivery_dashboard_test_fault(request)
    root = _request_project_root(request)
    try:
        project = load_project_status(project_root=root) if root else load_project_status()
        view = build_delivery_dashboard_view(project, project_root=root or PROJECT_ROOT)
    except PROJECT_STATUS_LOAD_ERRORS:
        return {
            "success": True,
            "data": {
                "schema_version": 1,
                "delivery_lines": [],
                "workspace_refs": {},
                "warnings": [
                    "交付线数据暂时无法通过完整性校验，已安全降级；"
                    "请由负责人核对 project-status.json 后再刷新。"
                ],
            },
        }
    return {"success": True, "data": view}


@router.get("/api/v1/project-status/dashboard/workspaces", include_in_schema=False)
def project_workspace_dashboard_data(request: Request) -> dict:
    """Return only the closed, management-safe workspace projection."""
    ensure_project_status_enabled()
    root = _request_project_root(request)
    try:
        project = load_project_status(project_root=root) if root else load_project_status()
        view = build_workspace_dashboard_view(project, project_root=root or PROJECT_ROOT)
    except PROJECT_STATUS_LOAD_ERRORS:
        return {
            "success": True,
            "data": {
                "schema_version": 1,
                "workspaces": [],
                "warnings": [
                    "工作区摘要暂时无法通过完整性校验，已安全降级；"
                    "当前未显示任何工作区状态。"
                ],
            },
        }
    return {"success": True, "data": view}


@router.get(
    "/api/v1/project-status/dashboard/delivery-lines/{line_id}/evidence/{evidence_id}",
    include_in_schema=False,
)
def project_delivery_evidence_data(line_id: str, evidence_id: str, request: Request) -> dict:
    """Expose only a safe evidence card for dashboard drill-down."""
    ensure_project_status_enabled()
    root = _request_project_root(request)
    try:
        return {
            "success": True,
            "data": load_delivery_evidence_view(
                line_id, evidence_id, project_root=root or PROJECT_ROOT
            ),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="DELIVERY_EVIDENCE_NOT_FOUND") from exc


@router.get(
    "/api/v1/project-status/dashboard/r3/workspaces/{workspace_id}",
    include_in_schema=False,
)
def project_r3_workspace_data(
    workspace_id: str, request: Request, line: str | None = None
) -> dict:
    """Return the controlled R3 workspace projection for the lightweight monitor."""
    ensure_project_status_enabled()
    if workspace_id not in WORKSPACE_ID_VALUES:
        raise HTTPException(status_code=404, detail="R3_WORKSPACE_NOT_FOUND")
    try:
        view = build_r3_workspace_view(
            workspace_id,
            line_id=line,
            project_root=_request_project_root(request) or PROJECT_ROOT,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="R3_LINE_NOT_FOUND") from exc
    return {"success": True, "data": view}


@router.get(
    "/api/v1/project-status/dashboard/r3/evidence/{evidence_type}/{evidence_id}",
    include_in_schema=False,
)
def project_r3_evidence_data(evidence_type: str, evidence_id: str, request: Request) -> dict:
    """Serve one safe evidence projection from the controlled target registry."""
    ensure_project_status_enabled()
    try:
        data = load_r3_evidence_detail(
            evidence_type,
            evidence_id,
            project_root=_request_project_root(request) or PROJECT_ROOT,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="R3_EVIDENCE_NOT_FOUND") from exc
    return {"success": True, "data": data}


@router.get("/project-status", response_class=HTMLResponse, include_in_schema=False)
def project_status_page(request: Request):
    ensure_project_status_enabled()
    root = _request_project_root(request)
    try:
        project = load_project_status(project_root=root) if root else load_project_status()
        delivery_dashboard = build_delivery_dashboard_view(
            project, project_root=root or PROJECT_ROOT
        )
    except PROJECT_STATUS_LOAD_ERRORS:
        return _render_degraded_project_status(request)
    return _templates_for(request).TemplateResponse(
        request,
        "project_status.html",
        {
            "project": project,
            "delivery_dashboard": delivery_dashboard,
            "status_labels": STATUS_LABELS,
            "delivery_state_labels": DELIVERY_STATE_LABELS,
        },
    )


@router.get("/api/v1/project-status/collaboration", include_in_schema=False)
def project_collaboration_data(request: Request) -> dict:
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    return {
        "success": True,
        "data": {
            "roles": project.get("roles", {}),
            "handoffs": project.get("handoffs", []),
        },
    }


@router.get("/api/v1/project-status/development", include_in_schema=False)
def project_development_workspace_data(request: Request) -> dict:
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    development = project.get("roles", {}).get("development", {})
    return {
        "success": True,
        "data": {
            "role": development,
            "document_groups": _resolve_workspace_document_groups(development),
            "handoffs": [
                handoff
                for handoff in project.get("handoffs", [])
                if "development" in (handoff.get("source"), handoff.get("target"))
            ],
        },
    }


@router.get("/api/v1/project-status/frontend", include_in_schema=False)
def project_frontend_workspace_data(request: Request) -> dict:
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    return {
        "success": True,
        "data": project.get("workspaces", {}).get("frontend", {}),
    }


@router.get(
    "/project-status/development",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_development_workspace_page(request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    development = project.get("roles", {}).get("development", {})
    document_groups = _resolve_workspace_document_groups(development)
    handoffs = [
        handoff
        for handoff in project.get("handoffs", [])
        if "development" in (handoff.get("source"), handoff.get("target"))
    ]
    return templates.TemplateResponse(
        request,
        "development_workspace.html",
        {
            "project": project,
            "development": development,
            "handoffs": handoffs,
            "document_groups": document_groups,
            "document_status_labels": DOCUMENT_STATUS_LABELS,
            "role_status_labels": ROLE_STATUS_LABELS,
            "handoff_status_labels": HANDOFF_STATUS_LABELS,
        },
    )


@router.get(
    "/project-status/frontend",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_frontend_workspace_page(request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    frontend = project.get("workspaces", {}).get("frontend", {})
    return templates.TemplateResponse(
        request,
        "frontend_workspace.html",
        {
            "project": project,
            "frontend": frontend,
            "role_status_labels": ROLE_STATUS_LABELS,
        },
    )


@router.get(
    "/project-status/collaboration",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_collaboration_page(request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    catalog = build_document_catalog()
    documents_by_path = {
        document["relative_path"]: document for document in catalog["documents"]
    }
    handoffs = [
        {
            **handoff,
            "document": documents_by_path.get(handoff.get("document_path")),
        }
        for handoff in project.get("handoffs", [])
    ]
    return templates.TemplateResponse(
        request,
        "collaboration.html",
        {
            "project": project,
            "roles": project.get("roles", {}),
            "handoffs": handoffs,
            "role_status_labels": ROLE_STATUS_LABELS,
            "handoff_status_labels": HANDOFF_STATUS_LABELS,
        },
    )


@router.get(
    "/project-status/workspaces",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def safe_workspace_overview_page(request: Request):
    """Standalone-panel entry for the closed workspace safety projection."""
    ensure_project_status_enabled()
    if not _is_standalone_panel(request):
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_ROUTE_CLOSED_OUTSIDE_PANEL")
    return _render_safe_workspace_page(request, "collaboration")


@router.get(
    "/project-status/workspaces/{workspace_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def safe_workspace_detail_page(workspace_id: str, request: Request):
    """Standalone-panel detail shell; browser fills it from one safe endpoint."""
    ensure_project_status_enabled()
    if not _is_standalone_panel(request):
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_ROUTE_CLOSED_OUTSIDE_PANEL")
    if workspace_id not in SAFE_WORKSPACE_PAGE_LABELS or workspace_id == "collaboration":
        raise HTTPException(status_code=404, detail="PROJECT_STATUS_WORKSPACE_NOT_FOUND")
    return _render_safe_workspace_page(request, workspace_id)


@router.get(
    "/project-status/technical-reviews",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_technical_reviews_page(request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    catalog = build_document_catalog()
    documents_by_path = {
        document["relative_path"]: document for document in catalog["documents"]
    }
    review_center = dict(project.get("technical_reviews", {}))
    review_center["reviews"] = [
        {
            **review,
            "document": documents_by_path.get(review.get("document_path")),
        }
        for review in review_center.get("reviews", [])
    ]
    return templates.TemplateResponse(
        request,
        "technical_reviews.html",
        {
            "project": project,
            "review_center": review_center,
            "review_status_labels": TECHNICAL_REVIEW_STATUS_LABELS,
        },
    )


@router.get("/project-status/documents", response_class=HTMLResponse, include_in_schema=False)
def project_documents_page(request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    return templates.TemplateResponse(
        request,
        "documents.html",
        {
            "project": load_project_status(),
            "catalog": build_document_catalog(),
            "document_status_labels": DOCUMENT_STATUS_LABELS,
        },
    )


@router.get(
    "/project-status/documents/{document_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_document_detail_page(document_id: str, request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    try:
        document = load_document(document_id)
        document_html = render_document(document)
        document_html = rewrite_document_links(
            document_html, document, build_document_catalog()["documents"]
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="PROJECT_DOCUMENT_NOT_FOUND") from exc
    return templates.TemplateResponse(
        request,
        "document_detail.html",
        {
            "project": load_project_status(),
            "document": document,
            "document_html": Markup(document_html),
            "document_status_labels": DOCUMENT_STATUS_LABELS,
        },
    )


@router.get(
    "/project-status/documents/{legacy_document_path:path}",
    include_in_schema=False,
)
def project_legacy_document_path(legacy_document_path: str, request: Request):
    """Keep historical relative Markdown links and bookmarks readable."""
    ensure_project_status_enabled()
    _panel_route_closed(request)
    document = next(
        (
            item
            for item in build_document_catalog()["documents"]
            if item["relative_path"] == legacy_document_path
        ),
        None,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="PROJECT_DOCUMENT_NOT_FOUND")
    return RedirectResponse(
        url=f"/project-status/documents/{document['id']}", status_code=307
    )


@router.get("/api/v1/project-status/tests", include_in_schema=False)
def project_test_status_data(request: Request) -> dict:
    ensure_project_status_enabled()
    _panel_route_closed(request)
    project = load_project_status()
    return {"success": True, "data": build_test_center(project)}


@router.get("/api/v1/project-status/tests/case-design", include_in_schema=False)
def project_case_design_data(request: Request) -> dict:
    """Return test-owned candidate Case design metadata, never formal Case totals."""
    ensure_project_status_enabled()
    return {
        "success": True,
        "data": build_case_design_center(project_root=_request_project_root(request))
    }


@router.get("/api/v1/project-status/test-automation", include_in_schema=False)
def project_test_automation_data(request: Request) -> dict:
    """Expose non-formal auxiliary UI automation summaries only."""
    ensure_project_status_enabled()
    return {
        "success": True,
        "data": build_test_automation_center(project_root=_request_project_root(request))
    }


@router.get(
    "/api/v1/project-status/test-automation/runs/{run_id}",
    include_in_schema=False,
)
def project_test_automation_run_data(run_id: str, request: Request) -> dict:
    """Expose one whitelisted auxiliary automation summary."""
    ensure_project_status_enabled()
    try:
        return {
            "success": True,
            "data": load_test_automation_run(
                run_id, project_root=_request_project_root(request)
            ),
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="TEST_AUTOMATION_RUN_NOT_FOUND") from exc


@router.get(
    "/api/v1/project-status/test-automation/runs/{run_id}/evidence/{evidence_id}",
    include_in_schema=False,
)
def project_test_automation_evidence_data(
    run_id: str, evidence_id: str, request: Request
) -> dict:
    """Map only an approved evidence id to its generated safe summary."""
    ensure_project_status_enabled()
    try:
        return {
            "success": True,
            "data": load_test_automation_evidence(
                run_id, evidence_id, project_root=_request_project_root(request)
            ),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="TEST_AUTOMATION_EVIDENCE_NOT_FOUND",
        ) from exc


@router.get(
    "/project-status/tests/automation",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_test_automation_page(request: Request):
    ensure_project_status_enabled()
    try:
        project = _load_project_status_for(request)
    except PROJECT_STATUS_LOAD_ERRORS:
        return _render_degraded_project_status(request)
    return _templates_for(request).TemplateResponse(
        request,
        "test_automation.html",
        {"project": project},
    )


@router.get(
    "/project-status/tests/automation/runs/{run_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_test_automation_run_page(run_id: str, request: Request):
    ensure_project_status_enabled()
    root = _request_project_root(request)
    try:
        load_test_automation_run(run_id, project_root=root)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="TEST_AUTOMATION_RUN_NOT_FOUND") from exc
    try:
        project = _load_project_status_for(request)
    except PROJECT_STATUS_LOAD_ERRORS:
        return _render_degraded_project_status(request)
    return _templates_for(request).TemplateResponse(
        request,
        "test_automation_run.html",
        {"project": project, "run_id": run_id.upper()},
    )


@router.get("/project-status/tests", response_class=HTMLResponse, include_in_schema=False)
def project_test_center_page(request: Request):
    ensure_project_status_enabled()
    root = _request_project_root(request)
    try:
        project = _load_project_status_for(request)
    except PROJECT_STATUS_LOAD_ERRORS:
        return _render_degraded_project_status(request)
    return _templates_for(request).TemplateResponse(
        request,
        "test_center.html",
        {
            "project": project,
            "test_center": build_test_center(project, project_root=root),
            "status_labels": STATUS_LABELS,
            "test_status_labels": TEST_STATUS_LABELS,
            "integration_status_labels": INTEGRATION_STATUS_LABELS,
            "defect_status_labels": DEFECT_STATUS_LABELS,
            "severity_labels": SEVERITY_LABELS,
        },
    )


@router.get(
    "/project-status/tests/case-design",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_case_design_page(request: Request):
    ensure_project_status_enabled()
    try:
        project = _load_project_status_for(request)
    except PROJECT_STATUS_LOAD_ERRORS:
        return _render_degraded_project_status(request)
    return _templates_for(request).TemplateResponse(
        request,
        "case_design.html",
        {
            "project": project,
            "case_design": build_case_design_center(project_root=_request_project_root(request)),
        },
    )


@router.get(
    "/project-status/tests/case-design/{task_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_case_design_detail_page(task_id: str, request: Request):
    ensure_project_status_enabled()
    try:
        task = load_case_design_task(
            task_id, project_root=_request_project_root(request)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="CASE_DESIGN_TASK_NOT_FOUND") from exc
    try:
        project = _load_project_status_for(request)
    except PROJECT_STATUS_LOAD_ERRORS:
        return _render_degraded_project_status(request)
    return _templates_for(request).TemplateResponse(
        request,
        "case_design_detail.html",
        {"project": project, "task": task},
    )


@router.get(
    "/project-status/stages/{stage_code}/tests",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_stage_tests_page(stage_code: str, request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    root = _request_project_root(request)
    try:
        project, stage = load_stage(stage_code, project_root=root or PROJECT_ROOT)
        cases = cases_with_latest_result(stage_code, project_root=root)
        summary = stage_test_summary(stage_code, project_root=root)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="PROJECT_STAGE_NOT_FOUND") from exc
    return templates.TemplateResponse(
        request,
        "stage_tests.html",
        {
            "project": project,
            "stage": stage,
            "cases": cases,
            "summary": summary,
            "runs": load_test_runs(stage_code, project_root=root),
            "defects": load_defects(stage_code, project_root=root),
            "integrations": load_test_integrations(project_root=root),
            "status_labels": STATUS_LABELS,
            "test_status_labels": TEST_STATUS_LABELS,
            "case_type_labels": CASE_TYPE_LABELS,
            "automation_status_labels": AUTOMATION_STATUS_LABELS,
            "result_status_labels": RESULT_STATUS_LABELS,
            "integration_status_labels": INTEGRATION_STATUS_LABELS,
            "defect_status_labels": DEFECT_STATUS_LABELS,
            "severity_labels": SEVERITY_LABELS,
        },
    )


@router.get(
    "/project-status/test-runs/{run_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_test_run_page(run_id: str, request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    root = _request_project_root(request)
    try:
        run = load_test_run(run_id, project_root=root)
        project, stage = load_stage(run["stage"], project_root=root or PROJECT_ROOT)
        case_lookup = {
            item["id"]: item
            for item in cases_with_latest_result(run["stage"], project_root=root)
        }
        case_type_summary = summarize_run_case_types(
            list(case_lookup.values()), run.get("case_results", [])
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="TEST_RUN_NOT_FOUND") from exc
    return templates.TemplateResponse(
        request,
        "test_run.html",
        {
            "project": project,
            "stage": stage,
            "run": run,
            "case_lookup": case_lookup,
            "case_type_summary": case_type_summary,
            "case_type_labels": CASE_TYPE_LABELS,
            "result_status_labels": RESULT_STATUS_LABELS,
        },
    )


@router.get("/project-status/defects", response_class=HTMLResponse, include_in_schema=False)
def project_defects_page(request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    root = _request_project_root(request)
    return templates.TemplateResponse(
        request,
        "defects.html",
        {
            "project": load_project_status(project_root=root) if root else load_project_status(),
            "defects": load_defects(project_root=root),
            "defect_status_labels": DEFECT_STATUS_LABELS,
            "severity_labels": SEVERITY_LABELS,
        },
    )


@router.get(
    "/project-status/defects/{defect_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_defect_detail_page(defect_id: str, request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    root = _request_project_root(request)
    try:
        defect = load_defect(defect_id, project_root=root)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="DEFECT_NOT_FOUND") from exc
    return templates.TemplateResponse(
        request,
        "defect_detail.html",
        {
            "project": load_project_status(project_root=root) if root else load_project_status(),
            "defect": defect,
            "defect_status_labels": DEFECT_STATUS_LABELS,
            "severity_labels": SEVERITY_LABELS,
        },
    )


@router.get(
    "/project-status/stages/{stage_code}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def project_stage_page(stage_code: str, request: Request):
    ensure_project_status_enabled()
    _panel_route_closed(request)
    root = _request_project_root(request)
    try:
        project, stage = load_stage(stage_code, project_root=root or PROJECT_ROOT)
        requirements_html = render_stage_requirements(stage_code, project_root=root or PROJECT_ROOT)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="PROJECT_STAGE_NOT_FOUND") from exc

    return templates.TemplateResponse(
        request,
        "project_stage.html",
        {
            "project": project,
            "stage": stage,
            "requirements_html": Markup(requirements_html),
            "status_labels": STATUS_LABELS,
            "test_status_labels": TEST_STATUS_LABELS,
        },
    )
