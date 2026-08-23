"""R4 质量工作区的受控、按需求测试生命周期投影。

本模块不解析原始 Markdown、日志或任意路径。它只读取
``project-status.json`` 中登记的 ``quality_workspace_r4`` 结构化映射，
将其重建为浏览器可消费的最小安全投影。候选 Case、生成任务和辅助
自动化始终与正式 Case 统计分离。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT

SECTION_KEY = "quality_workspace_r4"
REQUIREMENT_IDS = (
    "QR-MVP-A",
    "QR-MVP-B-MANUAL",
    "QR-MVP-B-TEXT-AI",
)
REQUIREMENT_STATUS_VALUES = frozenset(
    {
        "not_started",
        "designing",
        "executing",
        "blocked",
        "report_pending",
        "ready_for_product_acceptance",
        "archived",
    }
)
EXECUTION_STATUS_VALUES = frozenset(
    {"not_executed", "passed", "failed", "blocked", "not_applicable"}
)
AUTOMATION_STATUS_VALUES = frozenset(
    {
        "not_configured",
        "planned",
        "running",
        "passed_pending_human",
        "failed",
        "reviewed",
    }
)
DEFECT_STATUS_VALUES = frozenset(
    {
        "open",
        "confirmed",
        "in_progress",
        "ready_for_retest",
        "retest_partial",
        "retest_failed",
        "closed",
        "retest_passed",
    }
)
SEVERITY_VALUES = frozenset({"blocker", "critical", "high", "medium", "low"})
REPORT_STATUS_VALUES = frozenset({"not_available", "draft", "passed", "failed", "blocked"})
CANDIDATE_STATUS_VALUES = frozenset({"pending", "fixed", "inconsistent"})
CASE_TYPE_VALUES = frozenset({"functional", "regression", "manual", "integration"})
AUTOMATION_KIND_VALUES = frozenset({"manual", "automated", "hybrid"})

_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_STALE_AFTER = timedelta(hours=72)

REQUIREMENT_LABELS = {
    "not_started": "未开始",
    "designing": "测试设计中",
    "executing": "测试执行中",
    "blocked": "测试受阻",
    "report_pending": "待出具测试报告",
    "ready_for_product_acceptance": "可进入产品验收",
    "archived": "已归档",
}
EXECUTION_LABELS = {
    "not_executed": "未执行",
    "passed": "通过",
    "failed": "失败",
    "blocked": "阻塞",
    "not_applicable": "不适用",
}
AUTOMATION_LABELS = {
    "not_configured": "未配置",
    "planned": "待运行",
    "running": "运行中",
    "passed_pending_human": "辅助通过，待人工确认",
    "failed": "辅助运行失败",
    "reviewed": "已人工确认（辅助证据）",
}
DEFECT_STATUS_LABELS = {
    "open": "Open",
    "confirmed": "Open",
    "in_progress": "修复中",
    "ready_for_retest": "待复测",
    "retest_partial": "待复测",
    "retest_failed": "Open",
    "closed": "已关闭",
    "retest_passed": "已关闭",
}
REPORT_STATUS_LABELS = {
    "not_available": "尚未形成",
    "draft": "草稿",
    "passed": "通过",
    "failed": "失败",
    "blocked": "阻塞",
}


class QualityLifecycleNotFound(KeyError):
    """请求了未注册的质量需求。"""


def _warning(code: str, safe_message: str) -> dict[str, str]:
    return {"code": code, "safe_message": safe_message}


def _string(value: Any, *, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected non-empty string")
    value = value.strip()
    if len(value) > maximum or "file:" in value.lower() or "\\" in value:
        raise ValueError("unsafe string")
    return value


def _reference(value: Any) -> str:
    value = _string(value, maximum=128)
    if not _REFERENCE_PATTERN.fullmatch(value):
        raise ValueError("invalid reference")
    return value


def _iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _safe_timestamp(value: Any) -> str | None:
    parsed = _iso_datetime(value)
    if parsed is None or parsed > datetime.now(UTC):
        return None
    return value if isinstance(value, str) else None


def _stale(value: Any) -> bool:
    parsed = _iso_datetime(value)
    return parsed is not None and parsed <= datetime.now(UTC) - _STALE_AFTER


def _read_section(project_root: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = json.loads((project_root / "project-status.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, [_warning("QW_DATA_UNAVAILABLE", "暂时无法加载质量追踪信息，请稍后重试")]
    if not isinstance(payload, dict):
        return None, [_warning("QW_DATA_UNAVAILABLE", "暂时无法加载质量追踪信息，请稍后重试")]
    section = payload.get(SECTION_KEY)
    if section is None:
        return None, [_warning("QW_SECTION_MISSING", "测试资产待关联，当前不展示质量结论")]
    if not isinstance(section, dict):
        return None, [_warning("QW_DATA_UNAVAILABLE", "暂时无法加载质量追踪信息，请稍后重试")]
    return section, []


def _items(section: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    value = section.get(key, [])
    if not isinstance(value, list):
        return [], [_warning("QW_INVALID_DATA", "部分质量追踪信息格式无效，已安全忽略")]
    valid = [item for item in value if isinstance(item, dict)]
    warnings = (
        []
        if len(valid) == len(value)
        else [_warning("QW_INVALID_DATA", "部分质量追踪信息格式无效，已安全忽略")]
    )
    return valid, warnings


def _requirement(item: dict[str, Any]) -> dict[str, Any]:
    requirement_id = _reference(item.get("quality_requirement_id"))
    if requirement_id not in REQUIREMENT_IDS:
        raise ValueError("unregistered requirement")
    status = _string(item.get("status"), maximum=64)
    if status not in REQUIREMENT_STATUS_VALUES:
        raise ValueError("invalid requirement status")
    candidate_status = _string(item.get("candidate_status", "pending"), maximum=32)
    if candidate_status not in CANDIDATE_STATUS_VALUES:
        raise ValueError("invalid candidate status")
    refs: dict[str, list[str]] = {}
    for key in (
        "prd_refs",
        "feature_refs",
        "case_refs",
        "automation_refs",
        "defect_refs",
        "report_refs",
    ):
        raw = item.get(key, [])
        if not isinstance(raw, list):
            raise ValueError("invalid refs")
        refs[key] = [_reference(value) for value in raw]
    return {
        "quality_requirement_id": requirement_id,
        "delivery_line_id": _reference(item.get("delivery_line_id")),
        "name": _string(item.get("name")),
        "sort_order": item.get("sort_order"),
        "status": status,
        "scope_summary": _string(item.get("scope_summary")),
        "candidate_ref": _reference(item.get("candidate_ref", "PENDING")),
        "candidate_status": candidate_status,
        "verified_at": _safe_timestamp(item.get("verified_at")),
        **refs,
    }


def _case(item: dict[str, Any]) -> dict[str, Any]:
    case_type = _string(item.get("case_type"), maximum=32)
    automation_kind = _string(item.get("automation_kind"), maximum=32)
    if case_type not in CASE_TYPE_VALUES or automation_kind not in AUTOMATION_KIND_VALUES:
        raise ValueError("invalid case category")
    return {
        "case_id": _reference(item.get("case_id")),
        "quality_requirement_id": _reference(item.get("quality_requirement_id")),
        "requirement_ids": [_reference(value) for value in item.get("requirement_ids", [])],
        "feature_ids": [_reference(value) for value in item.get("feature_ids", [])],
        "title": _string(item.get("title")),
        "case_type": case_type,
        "automation_kind": automation_kind,
        "preconditions": _string(item.get("preconditions", "未提供"), maximum=500),
        "steps": _string(item.get("steps", "未提供"), maximum=800),
        "expected_result": _string(item.get("expected_result", "未提供"), maximum=800),
    }


def _execution(item: dict[str, Any]) -> dict[str, Any]:
    status = _string(item.get("execution_status"), maximum=32)
    if status not in EXECUTION_STATUS_VALUES:
        raise ValueError("invalid execution status")
    return {
        "case_id": _reference(item.get("case_id")),
        "run_id": _reference(item.get("run_id")),
        "execution_status": status,
        "executed_at": _safe_timestamp(item.get("executed_at")),
        "candidate_ref": _reference(item.get("candidate_ref")),
    }


def _automation(item: dict[str, Any]) -> dict[str, Any]:
    status = _string(item.get("automation_status"), maximum=32)
    if status not in AUTOMATION_STATUS_VALUES:
        raise ValueError("invalid automation status")
    total, failed = item.get("assertion_total", 0), item.get("assertion_failed", 0)
    if (
        any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (total, failed)
        )
        or failed > total
    ):
        raise ValueError("invalid assertion counts")
    return {
        "automation_run_id": _reference(item.get("automation_run_id")),
        "quality_requirement_id": _reference(item.get("quality_requirement_id")),
        "case_ids": [_reference(value) for value in item.get("case_ids", [])],
        "feature_ids": [_reference(value) for value in item.get("feature_ids", [])],
        "automation_status": status,
        "assertion_total": total,
        "assertion_failed": failed,
        "screenshot_registered": item.get("screenshot_registered") is True,
        "log_summary_registered": item.get("log_summary_registered") is True,
        "executed_at": _safe_timestamp(item.get("executed_at")),
        "human_reviewed_at": _safe_timestamp(item.get("human_reviewed_at")),
        "safe_summary": _string(item.get("safe_summary", "未提供辅助摘要")),
    }


def _defect(item: dict[str, Any]) -> dict[str, Any]:
    status = _string(item.get("status"), maximum=32)
    severity = _string(item.get("severity"), maximum=32)
    if status not in DEFECT_STATUS_VALUES or severity not in SEVERITY_VALUES:
        raise ValueError("invalid defect")
    jira = item.get("jira_issue_key")
    return {
        "defect_id": _reference(item.get("defect_id")),
        "quality_requirement_id": _reference(item.get("quality_requirement_id")),
        "jira_issue_key": _reference(jira) if jira else None,
        "severity": severity,
        "status": status,
        "case_ids": [_reference(value) for value in item.get("case_ids", [])],
        "report_ids": [_reference(value) for value in item.get("report_ids", [])],
        "candidate_ref": _reference(item.get("candidate_ref", "PENDING")),
        "retest_status": _string(item.get("retest_status", "未提供"), maximum=80),
        "safe_summary": _string(item.get("safe_summary", "未提供缺陷摘要")),
    }


def _report(item: dict[str, Any]) -> dict[str, Any]:
    status = _string(item.get("report_status"), maximum=32)
    if status not in REPORT_STATUS_VALUES:
        raise ValueError("invalid report")
    return {
        "report_id": _reference(item.get("report_id")),
        "quality_requirement_id": _reference(item.get("quality_requirement_id")),
        "candidate_ref": _reference(item.get("candidate_ref")),
        "scope_summary": _string(item.get("scope_summary")),
        "conclusion": _string(item.get("conclusion")),
        "report_status": status,
        "verified_at": _safe_timestamp(item.get("verified_at")),
    }


def _parse(
    section: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    requirements: dict[str, dict[str, Any]] = {}
    raw_requirements, item_warnings = _items(section, "requirements")
    warnings.extend(item_warnings)
    for item in raw_requirements:
        try:
            parsed = _requirement(item)
            if parsed["quality_requirement_id"] in requirements:
                raise ValueError("duplicate requirement")
            requirements[parsed["quality_requirement_id"]] = parsed
        except (TypeError, ValueError):
            warnings.append(
                _warning("QW_INVALID_REQUIREMENT", "部分质量需求未通过完整性校验，已安全忽略")
            )
    records: dict[str, list[dict[str, Any]]] = {}
    for key, parser in (
        ("formal_cases", _case),
        ("case_executions", _execution),
        ("automation_runs", _automation),
        ("defects", _defect),
        ("final_reports", _report),
    ):
        raw, item_warnings = _items(section, key)
        warnings.extend(item_warnings)
        parsed_items = []
        for item in raw:
            try:
                parsed_items.append(parser(item))
            except (TypeError, ValueError):
                warnings.append(
                    _warning("QW_INVALID_ASSET", "部分测试资产未通过完整性校验，已安全忽略")
                )
        records[key] = parsed_items
    return (
        requirements,
        records,
        list({(item["code"], item["safe_message"]): item for item in warnings}.values()),
    )


def _open_high_priority(defects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closed = {"closed", "retest_passed"}
    return [
        item
        for item in defects
        if item["status"] not in closed and item["severity"] in {"blocker", "critical", "high"}
    ]


def _execution_for(
    cases: list[dict[str, Any]], executions: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    known = {case["case_id"] for case in cases}
    selected: dict[str, dict[str, Any]] = {}
    for execution in executions:
        case_id = execution["case_id"]
        if case_id not in known:
            continue
        current = selected.get(case_id)
        if current is None or (execution["executed_at"] or "") >= (current["executed_at"] or ""):
            selected[case_id] = execution
    return selected


def _case_card(cases: list[dict[str, Any]], executions: list[dict[str, Any]]) -> dict[str, Any]:
    latest = _execution_for(cases, executions)
    counts = Counter(item["execution_status"] for item in latest.values())
    counts["not_executed"] += len(cases) - len(latest)
    return {
        "total": len(cases),
        "executed": sum(counts[key] for key in ("passed", "failed", "blocked")),
        "not_executed": counts["not_executed"],
        "passed": counts["passed"],
        "failed": counts["failed"],
        "blocked": counts["blocked"],
        "automated": sum(item["automation_kind"] == "automated" for item in cases),
        "manual": sum(item["automation_kind"] != "automated" for item in cases),
        "latest_execution_status": next(
            (item["execution_status"] for item in latest.values()), "not_executed"
        ),
    }


def _automation_card(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["automation_status"] for item in items)
    latest = max(items, key=lambda item: item["executed_at"] or "", default=None)
    return {
        "automatable_count": len(items),
        "latest_run_id": latest["automation_run_id"] if latest else None,
        "latest_status": latest["automation_status"] if latest else "not_configured",
        "passed_pending_human": counts["passed_pending_human"],
        "failed": counts["failed"],
        "reviewed": counts["reviewed"],
        "screenshot_summary": "已登记"
        if any(item["screenshot_registered"] for item in items)
        else "未登记",
        "log_summary": "已登记"
        if any(item["log_summary_registered"] for item in items)
        else "未登记",
        "boundary_statement": "辅助自动化，不等于正式准出",
    }


def _defect_card(items: list[dict[str, Any]]) -> dict[str, Any]:
    bucket = Counter()
    severity = Counter(item["severity"] for item in items)
    for item in items:
        bucket[DEFECT_STATUS_LABELS[item["status"]]] += 1
    open_items = [item for item in items if item["status"] not in {"closed", "retest_passed"}]
    open_high = _open_high_priority(items)
    highest = next(
        (
            level
            for level in ("blocker", "critical", "high", "medium", "low")
            if any(item["severity"] == level for item in open_items)
        ),
        None,
    )
    return {
        "total": len(items),
        "open": bucket["Open"],
        "in_progress": bucket["修复中"],
        "ready_for_retest": bucket["待复测"],
        "closed": bucket["已关闭"],
        "severity": {
            level: severity[level] for level in ("blocker", "critical", "high", "medium", "low")
        },
        "highest_open_severity": next(
            (item["severity"] for item in _open_high_priority(items)), highest
        ),
        "has_open_high_priority": bool(open_high),
    }


def _readiness(
    requirement: dict[str, Any],
    case_card: dict[str, Any],
    defects: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_fixed = requirement["candidate_status"] == "fixed"
    matching_reports = [
        item for item in reports if item["candidate_ref"] == requirement["candidate_ref"]
    ]
    passed_report = next(
        (
            item
            for item in matching_reports
            if item["report_status"] == "passed"
            and item["verified_at"]
            and not _stale(item["verified_at"])
        ),
        None,
    )
    blocking_case = case_card["blocked"] > 0
    high_defect = bool(_open_high_priority(defects))
    report_blocked = any(item["report_status"] == "blocked" for item in reports)
    verified = requirement["verified_at"] is not None and not _stale(requirement["verified_at"])
    has_formal_cases = case_card["total"] > 0
    eligible = bool(
        passed_report
        and candidate_fixed
        and has_formal_cases
        and not blocking_case
        and not high_defect
        and verified
    )
    if eligible:
        summary = "仅具备进入产品验收前提，P8-min 与产品验收另行判断"
    elif not has_formal_cases:
        summary = "尚未登记正式 Case，当前不可进入产品验收"
    elif not reports:
        summary = "尚未形成最终测试报告，当前不可进入产品验收"
    elif requirement["candidate_status"] == "inconsistent":
        summary = "候选不一致，状态待核对"
    elif blocking_case or report_blocked:
        summary = "存在阻塞测试资产，当前不可进入产品验收"
    elif high_defect:
        summary = "存在未关闭高优先级缺陷，当前不可进入产品验收"
    elif not passed_report:
        summary = "最终测试报告尚未有效通过，当前不可进入产品验收"
    else:
        summary = "测试负责人核对日期待补录或待复核，当前不可进入产品验收"
    return {
        "can_enter_product_acceptance": eligible,
        "safe_summary": summary,
        "matched_report_id": passed_report["report_id"] if passed_report else None,
        "is_blocked": bool(
            blocking_case
            or report_blocked
            or high_defect
            or requirement["candidate_status"] == "inconsistent"
        ),
    }


def _safe_case(case: dict[str, Any], execution: dict[str, Any] | None) -> dict[str, Any]:
    return {
        **case,
        "latest_execution": (
            {
                "run_id": execution["run_id"],
                "execution_status": execution["execution_status"],
                "execution_status_label": EXECUTION_LABELS[execution["execution_status"]],
                "executed_at": execution["executed_at"],
                "candidate_ref": execution["candidate_ref"],
            }
            if execution
            else None
        ),
    }


def _safe_requirement(requirement: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    status = requirement["status"]
    if not readiness["can_enter_product_acceptance"] and status == "ready_for_product_acceptance":
        status = "blocked" if readiness["is_blocked"] else "report_pending"
    return {
        "quality_requirement_id": requirement["quality_requirement_id"],
        "delivery_line_id": requirement["delivery_line_id"],
        "name": requirement["name"],
        "sort_order": requirement["sort_order"],
        "status": status,
        "status_label": REQUIREMENT_LABELS[status],
        "scope_summary": requirement["scope_summary"],
        "candidate_ref": requirement["candidate_ref"],
        "candidate_status": requirement["candidate_status"],
        "verified_at": requirement["verified_at"],
        "can_enter_product_acceptance": readiness["can_enter_product_acceptance"],
        "readiness_summary": readiness["safe_summary"],
    }


def _load(
    project_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    section, warnings = _read_section(project_root)
    if section is None:
        return (
            {},
            {
                key: []
                for key in (
                    "formal_cases",
                    "case_executions",
                    "automation_runs",
                    "defects",
                    "final_reports",
                )
            },
            warnings,
        )
    requirements, records, parsed_warnings = _parse(section)
    return requirements, records, warnings + parsed_warnings


def _selected_requirement(
    requirements: dict[str, dict[str, Any]], requirement_id: str | None
) -> dict[str, Any]:
    if requirement_id is None:
        for item_id in REQUIREMENT_IDS:
            if item_id in requirements:
                return requirements[item_id]
        raise QualityLifecycleNotFound("no registered quality requirement")
    if requirement_id not in requirements:
        raise QualityLifecycleNotFound(requirement_id)
    return requirements[requirement_id]


def build_quality_requirement_overview(
    *,
    project_root: Path = PROJECT_ROOT,
    requirement_id: str | None = None,
    line_id: str | None = None,
) -> dict[str, Any]:
    """Return the four-card R4 overview, or a safe empty projection."""
    requirements, records, warnings = _load(project_root)
    if not requirements:
        return {
            "requirements": [],
            "selected_requirement": None,
            "cards": _empty_cards(),
            "warnings": warnings,
        }
    requirement = _selected_requirement(requirements, requirement_id)
    if line_id is not None and line_id != requirement["delivery_line_id"]:
        return {
            "requirements": [_tab(item) for item in _ordered_requirements(requirements)],
            "selected_requirement": None,
            "cards": _empty_cards(),
            "warnings": warnings
            + [_warning("QW_REQUIREMENT_LINE_MISMATCH", "需求与交付线不匹配，请重新选择")],
            "state": "mismatch",
        }
    assets = _assets_for(requirement["quality_requirement_id"], records)
    case_card = _case_card(assets["formal_cases"], assets["case_executions"])
    readiness = _readiness(requirement, case_card, assets["defects"], assets["final_reports"])
    if not assets["formal_cases"]:
        warnings.append(_warning("QW_NO_FORMAL_CASES", "尚未登记正式 Case"))
    if not assets["final_reports"]:
        warnings.append(
            _warning("QW_NO_FINAL_REPORT", "尚未形成最终测试报告，当前不可进入产品验收")
        )
    return {
        "requirements": [_tab(item) for item in _ordered_requirements(requirements)],
        "selected_requirement": _safe_requirement(requirement, readiness),
        "cards": {
            "formal_cases": case_card,
            "assisted_automation": _automation_card(assets["automation_runs"]),
            "defects": _defect_card(assets["defects"]),
            "final_report": _report_card(assets["final_reports"], readiness),
        },
        "warnings": _dedupe_warnings(warnings),
        "state": "ready",
    }


def build_quality_requirement_detail(
    requirement_id: str, *, project_root: Path = PROJECT_ROOT, line_id: str | None = None
) -> dict[str, Any]:
    """Return the safe single-page detail sections for a registered quality requirement."""
    overview = build_quality_requirement_overview(
        project_root=project_root, requirement_id=requirement_id, line_id=line_id
    )
    if overview.get("state") == "mismatch":
        return overview
    requirements, records, _ = _load(project_root)
    requirement = _selected_requirement(requirements, requirement_id)
    assets = _assets_for(requirement_id, records)
    executions = _execution_for(assets["formal_cases"], assets["case_executions"])
    return {
        **overview,
        "sections": {
            "overview": {
                "prd_refs": requirement["prd_refs"],
                "feature_refs": requirement["feature_refs"],
                "scope_summary": requirement["scope_summary"],
            },
            "cases": [
                _safe_case(item, executions.get(item["case_id"])) for item in assets["formal_cases"]
            ],
            "automation": [_safe_automation(item) for item in assets["automation_runs"]],
            "defects": [_safe_defect(item) for item in assets["defects"]],
            "reports": [_safe_report(item) for item in assets["final_reports"]],
            "traceability": _traceability(requirement, assets, executions),
        },
    }


def _assets_for(
    requirement_id: str, records: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    assets = {
        key: [item for item in values if item.get("quality_requirement_id") == requirement_id]
        for key, values in records.items()
        if key != "case_executions"
    }
    case_ids = {item["case_id"] for item in assets["formal_cases"]}
    assets["case_executions"] = [
        item for item in records["case_executions"] if item["case_id"] in case_ids
    ]
    return assets


def _ordered_requirements(requirements: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        requirements.values(),
        key=lambda item: (
            REQUIREMENT_IDS.index(item["quality_requirement_id"]),
            item["sort_order"],
        ),
    )


def _tab(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "quality_requirement_id": item["quality_requirement_id"],
        "delivery_line_id": item["delivery_line_id"],
        "name": item["name"],
        "sort_order": item["sort_order"],
    }


def _empty_cards() -> dict[str, Any]:
    return {
        "formal_cases": {
            "total": 0,
            "executed": 0,
            "not_executed": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "automated": 0,
            "manual": 0,
            "latest_execution_status": "not_executed",
        },
        "assisted_automation": _automation_card([]),
        "defects": _defect_card([]),
        "final_report": {
            "report_id": None,
            "candidate_ref": None,
            "scope_summary": None,
            "conclusion": None,
            "report_status": "not_available",
            "can_enter_product_acceptance": False,
            "safe_summary": "尚未形成最终测试报告，当前不可进入产品验收",
        },
    }


def _report_card(reports: list[dict[str, Any]], readiness: dict[str, Any]) -> dict[str, Any]:
    selected = max(reports, key=lambda item: item["verified_at"] or "", default=None)
    if selected is None:
        return {
            "report_id": None,
            "candidate_ref": None,
            "scope_summary": None,
            "conclusion": None,
            "report_status": "not_available",
            "report_status_label": REPORT_STATUS_LABELS["not_available"],
            "can_enter_product_acceptance": False,
            "safe_summary": readiness["safe_summary"],
        }
    return {
        **_safe_report(selected),
        "can_enter_product_acceptance": readiness["can_enter_product_acceptance"],
        "safe_summary": readiness["safe_summary"],
    }


def _safe_automation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "automation_status_label": AUTOMATION_LABELS[item["automation_status"]],
        "boundary_statement": "辅助自动化，不等于正式准出",
    }


def _safe_defect(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "status_label": DEFECT_STATUS_LABELS[item["status"]],
        "is_open": item["status"] not in {"closed", "retest_passed"},
    }


def _safe_report(item: dict[str, Any]) -> dict[str, Any]:
    return {**item, "report_status_label": REPORT_STATUS_LABELS[item["report_status"]]}


def _traceability(
    requirement: dict[str, Any],
    assets: dict[str, list[dict[str, Any]]],
    executions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "prd_refs": requirement["prd_refs"],
        "feature_refs": requirement["feature_refs"],
        "case_ids": [item["case_id"] for item in assets["formal_cases"]],
        "execution_case_ids": sorted(executions),
        "defect_ids": [item["defect_id"] for item in assets["defects"]],
        "report_ids": [item["report_id"] for item in assets["final_reports"]],
    }


def _dedupe_warnings(items: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item["code"], item["safe_message"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
