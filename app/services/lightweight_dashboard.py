"""Small, file-backed projections for the local project delivery dashboard.

This is intentionally a presentation adapter, not a second project-management
domain.  The source remains ``project-status.json`` and all page content is
rebuilt from a small allow-list so that changing the data file does not require
changing templates or JavaScript.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.services.dashboard_contract import (
    AUTOMATION_STATUS_VALUES,
    CANDIDATE_VERSION_STATUS_LABELS,
    CONTRACT_STATUS_LABELS,
    DEFECT_STATUS_VALUES,
    DELIVERY_STATUS_LABELS,
    EVIDENCE_LEVEL_LABELS,
    QUALITY_CANDIDATE_STATUS_VALUES,
    QUALITY_REQUIREMENT_STATUS_VALUES,
    ROLE_STATUS_LABELS,
    RUNTIME_GATE_STATUS_LABELS,
    SOURCE_ROLE_LABELS,
    TEST_CASE_STATUS_VALUES,
    TEST_REPORT_STATUS_VALUES,
    TEST_RUN_STATUS_VALUES,
    delivery_line_relation_warnings,
    safe_status,
)
from app.services.project_status_cache import load_project_status

PAGE_VALUES = frozenset({"overview", "product", "frontend", "development", "testing"})
PAGE_LABELS = {
    "overview": "项目总览",
    "product": "产品 / PRD",
    "frontend": "前端交付",
    "development": "服务端交付",
    "testing": "质量 / 测试",
}
STATUS_LABELS = {
    "approved": "已确认",
    "confirmed": "已确认",
    "completed": "已完成",
    "done": "已完成",
    "in_progress": "进行中",
    "implementation": "进行中",
    "preparing": "准备中",
    "pending": "待确认",
    "planned": "未开始",
    "product_acceptance": "待确认",
    "open": "已阻断",
    "not_frozen": "待确认",
    "not_fixed": "待确认",
    "not_assessed": "待核对",
    "evidence_ready": "已确认",
    "draft": "待确认",
    "assessed": "已评估",
}
STATUS_LABELS.update(ROLE_STATUS_LABELS)
STATUS_LABELS.update(DELIVERY_STATUS_LABELS)


def _safe_text(value: Any, fallback: str = "待关联", *, maximum: int = 600) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    value = value.strip()
    lowered = value.lower()
    if (
        len(value) > maximum
        or "file:" in lowered
        or "http://" in lowered
        or "https://" in lowered
        or "\\" in value
        or "\r" in value
        or "\n" in value
    ):
        return fallback
    return value


def _safe_id(value: Any, fallback: str = "") -> str:
    value = _safe_text(value, fallback, maximum=128)
    return value if value and all(char.isalnum() or char in "_.:-" for char in value) else fallback


def _status(
    value: Any,
    *,
    field: str,
    labels: dict[str, str] | None = None,
    warnings: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    projected, warning = safe_status(value, field=field, labels=labels or STATUS_LABELS)
    if warning is not None and warnings is not None:
        warnings.append(warning)
    return projected


def _optional_status(
    value: Any,
    *,
    field: str,
    labels: dict[str, str],
    warnings: list[dict[str, str]],
) -> dict[str, str]:
    if value is None or value == "":
        return {"code": "pending_check", "label": "待关联"}
    return _status(value, field=field, labels=labels, warnings=warnings)


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "safe_message": message}


def _quality_items(
    section: dict[str, Any],
    key: str,
    enum_fields: dict[str, frozenset[str]],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Return only quality objects whose registered enum fields are valid."""
    raw_items = section.get(key, [])
    if not isinstance(raw_items, list):
        warnings.append(
            {
                "code": "DASHBOARD_INVALID_QUALITY_DATA",
                "field": f"quality_workspace_r4.{key}",
                "safe_message": f"quality_workspace_r4.{key} 格式待核对",
            }
        )
        return []

    valid: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        field_root = f"quality_workspace_r4.{key}[{index}]"
        if not isinstance(item, dict):
            warnings.append(
                {
                    "code": "DASHBOARD_INVALID_QUALITY_DATA",
                    "field": field_root,
                    "safe_message": f"{field_root} 格式待核对",
                }
            )
            continue
        invalid_fields = [
            field for field, allowed in enum_fields.items() if item.get(field) not in allowed
        ]
        if invalid_fields:
            warnings.extend(
                {
                    "code": "DASHBOARD_UNKNOWN_ENUM",
                    "field": f"{field_root}.{field}",
                    "safe_message": f"{field_root}.{field} 状态待核对",
                }
                for field in invalid_fields
            )
            continue
        valid.append(item)
    return valid


def _load(project_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    try:
        payload = load_project_status(project_root).payload
    except (OSError, UnicodeDecodeError, ValueError):
        return {}, [_warning("DASHBOARD_DATA_UNAVAILABLE", "项目状态暂时无法加载")]
    if not isinstance(payload, dict):
        return {}, [_warning("DASHBOARD_DATA_UNAVAILABLE", "项目状态格式无效")]
    return payload, []


def _delivery_lines(
    payload: dict[str, Any], warnings: list[dict[str, str]]
) -> list[dict[str, Any]]:
    result = []
    for raw in _list(payload.get("delivery_lines")):
        if not isinstance(raw, dict):
            continue
        line_id = _safe_id(raw.get("delivery_line_id") or raw.get("id"))
        if not line_id:
            continue
        blockers = [item for item in _list(raw.get("open_blockers")) if isinstance(item, dict)]
        field = f"delivery_lines[{len(result)}]"
        status_source = raw.get("delivery_status") or raw.get("status")
        status_labels = (
            DELIVERY_STATUS_LABELS
            if raw.get("delivery_status") is not None
            else STATUS_LABELS
        )
        evidence_level, level_warning = safe_status(
            raw.get("evidence_level"), field=f"{field}.evidence_level", labels=EVIDENCE_LEVEL_LABELS
        )
        if raw.get("evidence_level") is None:
            evidence_level, level_warning = ({"code": "pending_check", "label": "待关联"}, None)
        if level_warning:
            warnings.append(level_warning)
        for relation_warning in delivery_line_relation_warnings(raw, field=field):
            warnings.append(relation_warning)
        contract = _mapping(raw.get("contract_state"))
        candidate = _mapping(raw.get("candidate_version"))
        runtime = _mapping(raw.get("runtime_gate"))
        source_role = _optional_status(
            raw.get("source_role"),
            field=f"{field}.source_role",
            labels=SOURCE_ROLE_LABELS,
            warnings=warnings,
        )
        result.append(
            {
                "delivery_line_id": line_id,
                "name": _safe_text(raw.get("name") or raw.get("display_label")),
                "scope_summary": _safe_text(raw.get("scope_summary") or raw.get("summary")),
                "status": _status(
                    status_source,
                    field=f"{field}.delivery_status",
                    labels=status_labels,
                    warnings=warnings,
                ),
                "evidence_level": evidence_level,
                "contract_state": _optional_status(
                    contract.get("status"),
                    field=f"{field}.contract_state.status",
                    labels=CONTRACT_STATUS_LABELS,
                    warnings=warnings,
                ),
                "candidate_version": _optional_status(
                    candidate.get("status"),
                    field=f"{field}.candidate_version.status",
                    labels=CANDIDATE_VERSION_STATUS_LABELS,
                    warnings=warnings,
                ),
                "runtime_gate": _optional_status(
                    runtime.get("status"),
                    field=f"{field}.runtime_gate.status",
                    labels=RUNTIME_GATE_STATUS_LABELS,
                    warnings=warnings,
                ),
                "display_label": _safe_text(raw.get("display_label")),
                "summary": _safe_text(raw.get("summary")),
                "source_role": source_role["code"],
                "source_role_label": source_role["label"],
                "verified_at": _safe_text(raw.get("verified_at")),
                "updated_at": _safe_text(raw.get("updated_at")),
                "blocker_count": len(blockers),
                "next_action": _safe_text(
                    blockers[0].get("next_action") if blockers else None,
                    "下一步待关联",
                ),
            }
        )
    return result


def _selected_line(lines: list[dict[str, Any]], line_id: str | None) -> dict[str, Any] | None:
    if line_id is None:
        return lines[0] if lines else None
    return next((line for line in lines if line["delivery_line_id"] == line_id), None)


def _role_summary(
    payload: dict[str, Any], role: str, warnings: list[dict[str, str]]
) -> dict[str, Any]:
    roles = _mapping(payload.get("roles"))
    raw = _mapping(roles.get(role))
    field_prefix = f"roles.{role}.status"
    if not raw and role == "frontend":
        workspaces = _mapping(payload.get("workspaces"))
        raw = _mapping(workspaces.get("frontend"))
        field_prefix = "workspaces.frontend.status"
    name_fallback = "前端开发" if role == "frontend" else role
    return {
        "name": _safe_text(raw.get("name"), name_fallback),
        "status": _optional_status(
            raw.get("status"),
            field=field_prefix,
            labels=ROLE_STATUS_LABELS,
            warnings=warnings,
        ),
        "current": _safe_text(raw.get("current")),
        "next": _safe_text(raw.get("next")),
        "waiting_for": _safe_text(raw.get("waiting_for")),
        "integration_status": _safe_text(raw.get("integration_status")),
    }


def _workspace_summary(payload: dict[str, Any], role: str) -> dict[str, Any]:
    workspaces = _mapping(payload.get("workspaces"))
    return _mapping(workspaces.get(role))


def _overview(
    payload: dict[str, Any], lines: list[dict[str, Any]], warnings: list[dict[str, str]]
) -> dict[str, Any]:
    roadmap = _mapping(payload.get("product_roadmap"))
    decisions = []
    for raw in _list(payload.get("decisions"))[:5]:
        if not isinstance(raw, dict):
            continue
        decisions.append(
            {
                "decision_id": _safe_id(raw.get("decision_id") or raw.get("id"), ""),
                "title": _safe_text(raw.get("title")),
                "impact_summary": _safe_text(raw.get("impact_summary")),
                "owner_role": _safe_text(raw.get("owner_role")),
                "status": _status(raw.get("status"), field="decisions[].status"),
                "next_action": _safe_text(raw.get("next_action")),
            }
        )
    return {
        "direction": _safe_text(payload.get("current_focus") or roadmap.get("current_position")),
        "summary": _safe_text(payload.get("summary")),
        "overall_status": _status(payload.get("overall_status"), field="overall_status"),
        "progress_percent": (
            payload.get("progress_percent")
            if isinstance(payload.get("progress_percent"), (int, float))
            and not isinstance(payload.get("progress_percent"), bool)
            else None
        ),
        "progress_summary": _safe_text(roadmap.get("current_position")),
        "lines": lines,
        "decisions": decisions,
        "roles": {
            "frontend": _role_summary(payload, "frontend", warnings),
            "development": _role_summary(payload, "development", warnings),
            "testing": _role_summary(payload, "testing", warnings),
        },
        "recent_updates": [
            {
                "date": _safe_text(item.get("date")),
                "title": _safe_text(item.get("title")),
                "detail": _safe_text(item.get("detail")),
            }
            for item in _list(payload.get("recent_updates"))[:5]
            if isinstance(item, dict)
        ],
    }


def _product(payload: dict[str, Any], lines: list[dict[str, Any]]) -> dict[str, Any]:
    roadmap = _mapping(payload.get("product_roadmap"))
    release = _mapping(payload.get("release"))
    versions = []
    for raw in _list(roadmap.get("versions")):
        if not isinstance(raw, dict):
            continue
        versions.append(
            {
                "code": _safe_id(raw.get("code")),
                "title": _safe_text(raw.get("title")),
                "status": _status(raw.get("status"), field="product_roadmap.versions[].status"),
                "scope": _safe_text(raw.get("scope")),
                "next_gate": _safe_text(raw.get("next_gate")),
            }
        )
    return {
        "baseline": _safe_text(roadmap.get("baseline")),
        "source_document": (
            "产品基线来源已登记"
            if isinstance(roadmap.get("source_document"), str)
            and roadmap.get("source_document").strip()
            else "产品基线来源待关联"
        ),
        "current_position": _safe_text(roadmap.get("current_position")),
        "release": {
            "status": _status(release.get("status"), field="release.status"),
            "summary": _safe_text(release.get("summary")),
        },
        "versions": versions,
        "lines": lines,
    }


def _frontend(
    payload: dict[str, Any],
    lines: list[dict[str, Any]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    role = _role_summary(payload, "frontend", warnings)
    workspace = _workspace_summary(payload, "frontend")
    return {
        "role": role,
        "lines": lines,
        "browser_verification": _safe_text(workspace.get("browser_verification")),
        "blockers": _safe_text(workspace.get("blockers")),
    }


def _technical_reviews(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_reviews = _mapping(payload.get("technical_reviews")).get("reviews")
    result = []
    for raw in _list(raw_reviews):
        if not isinstance(raw, dict):
            continue
        result.append(
            {
                "review_id": _safe_id(raw.get("code")),
                "title": _safe_text(raw.get("title")),
                "scope": _safe_text(raw.get("scope")),
                "status": _status(raw.get("status"), field="technical_reviews.reviews[].status"),
                "next": _safe_text(raw.get("next")),
            }
        )
    return result


def _development(
    payload: dict[str, Any],
    lines: list[dict[str, Any]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    workspace = _workspace_summary(payload, "development")
    return {
        "role": _role_summary(payload, "development", warnings),
        "reviews": _technical_reviews(payload),
        "implementation_scope": _safe_text(workspace.get("implementation_scope")),
        "risks": _safe_text(workspace.get("risks")),
        "lines": lines,
    }


def _quality(
    payload: dict[str, Any], lines: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    quality_warnings: list[dict[str, str]] = []
    section = _mapping(payload.get("quality_workspace_r4"))
    if not section:
        return (
            {
                "state": "unlinked",
                "role": _role_summary(payload, "testing", quality_warnings),
                "requirements": None,
                "formal_cases": None,
                "executed": None,
                "passed": None,
                "failed": None,
                "blocked": None,
                "not_executed": None,
                "automation": None,
                "defects": None,
                "coverage": "覆盖关系待关联",
                "lines": lines,
            },
            quality_warnings + [_warning("DASHBOARD_QUALITY_UNLINKED", "质量统计待关联")],
        )
    requirements = _quality_items(
        section,
        "requirements",
        {
            "status": QUALITY_REQUIREMENT_STATUS_VALUES,
            "candidate_status": QUALITY_CANDIDATE_STATUS_VALUES,
        },
        quality_warnings,
    )
    cases = _quality_items(
        section,
        "formal_cases",
        {"case_status": TEST_CASE_STATUS_VALUES},
        quality_warnings,
    )
    executions = _quality_items(
        section,
        "case_executions",
        {"execution_status": TEST_RUN_STATUS_VALUES},
        quality_warnings,
    )
    automation = _quality_items(
        section,
        "automation_runs",
        {"automation_status": AUTOMATION_STATUS_VALUES},
        quality_warnings,
    )
    defects = _quality_items(
        section,
        "defects",
        {"status": DEFECT_STATUS_VALUES},
        quality_warnings,
    )
    _quality_items(
        section,
        "final_reports",
        {"report_status": TEST_REPORT_STATUS_VALUES},
        quality_warnings,
    )
    case_ids = {
        item.get("case_id") for item in cases if isinstance(item, dict) and item.get("case_id")
    }
    latest_executions: dict[str, dict[str, Any]] = {}
    for item in executions:
        if not isinstance(item, dict) or item.get("case_id") not in case_ids:
            continue
        case_id = item["case_id"]
        current = latest_executions.get(case_id)
        if current is None or str(item.get("executed_at", "")) >= str(
            current.get("executed_at", "")
        ):
            latest_executions[case_id] = item
    execution_statuses = Counter(
        item.get("execution_status") for item in latest_executions.values()
    )
    case_types = Counter(
        item.get("automation_kind") for item in cases if isinstance(item, dict)
    )
    open_defects = [
        item
        for item in defects
        if isinstance(item, dict) and item.get("status") not in {"closed", "retest_passed"}
    ]
    return (
        {
            "state": "pending_check" if quality_warnings else "ready",
            "role": _role_summary(payload, "testing", quality_warnings),
            "requirements": len(requirements),
            "formal_cases": len(cases),
            "executed": len(latest_executions),
            "passed": execution_statuses.get("passed", 0),
            "failed": execution_statuses.get("failed", 0),
            "blocked": execution_statuses.get("blocked", 0),
            "not_executed": max(len(cases) - len(latest_executions), 0),
            "automation": {
                "automated": case_types.get("automated", 0),
                "manual": case_types.get("manual", 0),
                "assisted_runs": len(automation),
            },
            "defects": {
                "open": len(open_defects),
                "total": len(defects),
                "lifecycle": dict(Counter(
                    item.get("status") for item in defects if isinstance(item, dict)
                )),
            },
            "coverage": "覆盖矩阵摘要待关联",
            "lines": lines,
        },
        quality_warnings,
    )


def build_lightweight_dashboard(
    *, page: str = "overview", line_id: str | None = None, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    if page not in PAGE_VALUES:
        raise KeyError(page)
    payload, warnings = _load(project_root)
    lines = _delivery_lines(payload, warnings)
    selected_line = _selected_line(lines, line_id)
    if line_id is not None and selected_line is None:
        raise KeyError(line_id)
    page_data: dict[str, Any]
    if page == "overview":
        page_data = _overview(payload, lines, warnings)
    elif page == "product":
        page_data = _product(payload, lines)
    elif page == "frontend":
        page_data = _frontend(payload, lines, warnings)
    elif page == "development":
        page_data = _development(payload, lines, warnings)
    else:
        page_data, quality_warnings = _quality(payload, lines)
        warnings.extend(quality_warnings)
    return {
        "schema_version": 1,
        "page": page,
        "page_label": PAGE_LABELS[page],
        "project": {
            "name": _safe_text(payload.get("project_name"), "项目名称待关联"),
            "updated_at": _safe_text(payload.get("last_updated")),
            "updated_display": _safe_text(payload.get("last_updated_display")),
        },
        "line_options": [
            {"id": line["delivery_line_id"], "label": line["name"]} for line in lines
        ],
        "selected_line": selected_line,
        "data": page_data,
        "warnings": warnings,
    }
