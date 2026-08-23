"""R3 轻量监控受控投影服务.

R3 只从 project-status.json 的 dashboard_r3 受控段读取数据，与旧
project_status.py 的 delivery_lines 兼容逻辑相互独立。所有输出字段闭合：
逐字段白名单重建，未知字段与原始资料内容一律不透传。

产品澄清结论（开工前已确认）：
- delivery_fact.status 枚举：verified / pending_check / stale；
- owner_role 仅允许 development / frontend / testing 三角色；
- verified_at 使用带时区 ISO 8601 字符串，按 72 小时判定待复核；
- evidence_targets[].status 枚举：valid / stale / missing；
- evidence_targets[].purpose 枚举：independent_test / product_acceptance /
  p8_min_runtime / reference。用途只在服务端准出判断使用，不透传原始资料。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.services.document_catalog import build_document_catalog
from app.services.test_management import (
    _is_valid_test_run,
    load_case_design_task,
    load_defects,
)

R3_SECTION_KEY = "dashboard_r3"
R3_SECTION_KEYS = frozenset(
    {
        "delivery_lines",
        "delivery_facts",
        "evidence_targets",
        "declared_candidate_combinations",
    }
)

DELIVERY_LINE_STATUS_VALUES = frozenset(
    {
        "planning",
        "contract_freeze",
        "implementation",
        "integration",
        "independent_test",
        "product_acceptance",
        "ready_for_trial",
    }
)
FACT_TYPE_VALUES = frozenset(
    {"completed", "in_progress", "next_action", "blocked", "candidate"}
)
FACT_STATUS_VALUES = frozenset({"verified", "pending_check", "stale"})
OWNER_ROLE_VALUES = frozenset({"development", "frontend", "testing"})
WORKSPACE_ID_VALUES = frozenset(
    {"collaboration", "development", "frontend", "testing"}
)
EVIDENCE_TYPE_VALUES = frozenset(
    {
        "document",
        "test_run",
        "case_design",
        "defect",
        "technical_review",
        "handoff",
        "stage",
    }
)
CANDIDATE_STATUS_VALUES = frozenset({"pending", "fixed", "inconsistent"})
EVIDENCE_TARGET_STATUS_VALUES = frozenset({"valid", "stale", "missing"})
EVIDENCE_PURPOSE_VALUES = frozenset(
    {"independent_test", "product_acceptance", "p8_min_runtime", "reference"}
)

CANDIDATE_PENDING_PLACEHOLDER = "待提供"
MIGRATION_NOT_APPLICABLE = "不适用"
INCONSISTENT_SAFE_SUMMARY = "候选不一致，状态待核对"

PROGRESS_FACT_TYPES = frozenset({"completed", "in_progress", "next_action"})
GATE_FACT_TYPES = frozenset({"blocked", "candidate"})

# DASH-LITE-003：准出必须按受控证据用途判断，不能只凭 document/handoff 或
# test_run 类型推断。否则无关交接或普通测试运行会误导为产品验收或 P8-min 证据。
PURPOSE_TYPE_VALUES = {
    "independent_test": frozenset({"test_run"}),
    "product_acceptance": frozenset({"document", "handoff"}),
    "p8_min_runtime": frozenset({"test_run"}),
    "reference": EVIDENCE_TYPE_VALUES,
}

STALE_AFTER = timedelta(hours=72)

SAFE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

DELIVERY_LINE_KEYS = frozenset(
    {
        "delivery_line_id",
        "name",
        "scope_summary",
        "delivery_status",
        "current_conclusion",
        "current_candidate_summary",
        "next_gate_summary",
        "can_enter_product_acceptance",
        "can_enter_controlled_trial",
        "verified_at",
    }
)
DELIVERY_FACT_COMMON_KEYS = frozenset(
    {
        "fact_id",
        "delivery_line_id",
        "fact_type",
        "status",
        "owner_role",
        "verified_at",
        "summary",
        "evidence_refs",
        "workspace_ids",
    }
)
CANDIDATE_CONTENT_KEYS = frozenset(
    {"backend_candidate", "frontend_candidate", "migration_summary", "startup_handoff_ref"}
)
CANDIDATE_EXTRA_KEYS = CANDIDATE_CONTENT_KEYS | {"candidate_status"}
EVIDENCE_TARGET_KEYS = frozenset(
    {
        "type",
        "id",
        "title",
        "status",
        "purpose",
        "owner_role",
        "verified_at",
        "safe_summary",
        "related_evidence_ids",
    }
)
EVIDENCE_REF_KEYS = frozenset({"type", "id"})
CANDIDATE_COMBINATION_KEYS = frozenset(
    {
        "delivery_line_id",
        "backend_candidate",
        "frontend_candidate",
        "migration_summary",
        "startup_handoff_ref",
    }
)

OWNER_ROLE_LABELS = {
    "development": "服务端技术负责人",
    "frontend": "前端开发负责人",
    "testing": "测试负责人",
}
WORKSPACE_LABELS = {
    "collaboration": "协作总览",
    "development": "服务端工作区",
    "frontend": "前端工作区",
    "testing": "质量工作区",
}
DELIVERY_STATUS_LABELS = {
    "planning": "规划中",
    "contract_freeze": "契约待冻结",
    "implementation": "实施中",
    "integration": "联调中",
    "independent_test": "独立测试中",
    "product_acceptance": "产品验收中",
    "ready_for_trial": "可试用",
}
CANDIDATE_STATUS_LABELS = {
    "pending": "候选信息待补齐",
    "fixed": "候选组合已固定",
    "inconsistent": "候选不一致，状态待核对",
}

WARNING_MESSAGES = {
    "R3_SECTION_MISSING": "交付监控信息暂未建立，当前不展示任何通过或准出结论",
    "R3_DATA_UNAVAILABLE": "暂时无法加载交付信息，请稍后重试",
    "R3_INVALID_LINE": "部分交付线数据未通过完整性校验，已安全忽略",
    "R3_INVALID_FACT": "部分交付事实数据未通过完整性校验，已安全忽略",
    "R3_INVALID_TARGET": "部分证据目标数据未通过完整性校验，已安全忽略",
    "R3_INVALID_COMBINATION": "部分已声明候选组合未通过完整性校验，已安全忽略",
    "R3_INVALID_REF": "部分事实引用了非法证据编号，已安全忽略",
    "R3_FACT_STALE": "部分事实最近核对超过72小时，状态待复核",
    "R3_FACT_VERIFIED_AT_MISSING": "部分事实核对日期缺失或格式不正确，核对日期待补录",
    "R3_FACT_EVIDENCE_MISSING": "部分完成结论缺少有效证据，状态待核对",
    "R3_CANDIDATE_INCOMPLETE": "部分候选信息待补齐",
    "R3_CANDIDATE_UNMATCHED": (
        "部分候选组合与已声明组合不匹配或存在引用冲突，候选不一致，状态待核对"
    ),
    "R3_CANDIDATE_STATUS_MISMATCH": "部分候选声明状态与已提供候选字段冲突，候选不一致，状态待核对",
    "R3_LINE_FLAG_UNVERIFIED": "部分准出声明缺少有效证据，已降级为待核对",
    "R3_LINE_CANDIDATE_INCONSISTENT": "交付线存在候选不一致，不显示通过或可试用结论",
    "R3_LINE_TRIAL_UNVERIFIED": (
        "可试用结论缺少产品人工验收结论或P8-min运行证据，已降级为待核对"
    ),
    "R3_LINE_STALE": "部分交付线最近核对超过72小时，状态待复核",
    "R3_LINE_VERIFIED_AT_MISSING": "部分交付线核对日期缺失或格式不正确，核对日期待补录",
    "R3_LINE_NO_FACTS": "该交付线尚未建立监控事实",
}


class _R3LoadError(Exception):
    """根级数据失败：必须降级为安全空投影，不允许冒泡为 500。"""


class _R3SectionMissing(_R3LoadError):
    """project-status.json 尚未建立 dashboard_r3 段。"""


def _require_string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _reject_undeclared_fields(
    mapping: dict[str, Any], field: str, allowed: frozenset[str]
) -> None:
    extra = set(mapping) - allowed
    if extra:
        raise ValueError(f"{field} contains undeclared fields")


def _parse_verified_at(value: Any) -> datetime | None:
    """仅接受带时区 ISO 8601；无时区或无法解析一律视为缺失。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _verified_at_stale(value: Any) -> bool | None:
    """True=超过72小时；False=未超；None=缺失或格式错误。"""
    parsed = _parse_verified_at(value)
    if parsed is None:
        return None
    return datetime.now(timezone.utc) - parsed > STALE_AFTER


def _test_run_asset_resolves(run_id: str, project_root: Path) -> bool:
    """test_run 稳定编号必须追溯到受控运行资产。

    自动化阶段运行必须携带通过完整性校验的 summary.json；独立测试报告类
    运行目录（如 RUN-MVP-A-20260812-001000）以受控报告文件为登记依据。
    """
    run_dir = project_root / "reports" / "test-runs" / run_id
    if not run_dir.is_dir():
        return False
    summary_path = run_dir / "summary.json"
    if summary_path.is_file():
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False
        return _is_valid_test_run(payload)
    return any(run_dir.glob("*.md"))


def _handoff_asset_resolves(handoff_id: str, project_root: Path) -> bool:
    """handoff 稳定编号必须出现在已登记的正式交接记录中。"""
    handoffs_dir = project_root / "docs" / "internal" / "handoffs"
    if not handoffs_dir.is_dir():
        return False
    token_pattern = re.compile(rf"(?<![\w-]){re.escape(handoff_id)}(?![\w-])")
    for handoff_path in handoffs_dir.glob("*.md"):
        try:
            source = handoff_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if token_pattern.search(source):
            return True
    return False


def _defect_asset_resolves(defect_id: str, project_root: Path) -> bool:
    try:
        defects = load_defects(project_root=project_root)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return any(item.get("id") == defect_id for item in defects)


def _document_asset_resolves(document_id: str, project_root: Path) -> bool:
    try:
        documents = build_document_catalog(project_root)["documents"]
    except (OSError, KeyError):
        return False
    return any(item.get("id") == document_id for item in documents)


def _case_design_asset_resolves(task_id: str, project_root: Path) -> bool:
    try:
        load_case_design_task(task_id, project_root=project_root)
    except KeyError:
        return False
    return True


def _technical_review_asset_resolves(review_id: str, project_root: Path) -> bool:
    try:
        payload = json.loads(
            (project_root / "project-status.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    reviews = payload.get("technical_reviews", {})
    if not isinstance(reviews, dict):
        return False
    review_list = reviews.get("reviews", [])
    return any(
        isinstance(item, dict) and item.get("code") == review_id
        for item in review_list
        if isinstance(review_list, list)
    )


def _stage_asset_resolves(stage_code: str, project_root: Path) -> bool:
    try:
        payload = json.loads(
            (project_root / "project-status.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    stages = payload.get("stages")
    return any(
        isinstance(item, dict) and item.get("code") == stage_code
        for item in stages
        if isinstance(stages, list)
    )


def _resolve_controlled_asset(ref_type: str, ref_id: str, project_root: Path) -> bool:
    """确认稳定编号真实存在于受控项目资产；任何解析失败都视为未登记。"""
    try:
        if ref_type == "test_run":
            return _test_run_asset_resolves(ref_id, project_root)
        if ref_type == "handoff":
            return _handoff_asset_resolves(ref_id, project_root)
        if ref_type == "defect":
            return _defect_asset_resolves(ref_id, project_root)
        if ref_type == "document":
            return _document_asset_resolves(ref_id, project_root)
        if ref_type == "case_design":
            return _case_design_asset_resolves(ref_id, project_root)
        if ref_type == "technical_review":
            return _technical_review_asset_resolves(ref_id, project_root)
        if ref_type == "stage":
            return _stage_asset_resolves(ref_id, project_root)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return False


def _warning(code: str) -> dict[str, str]:
    return {"code": code, "safe_message": WARNING_MESSAGES[code]}


def _load_r3_section(project_root: Path) -> dict[str, Any]:
    status_path = project_root / "project-status.json"
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _R3LoadError("project-status.json cannot be loaded") from exc
    if not isinstance(payload, dict):
        raise _R3LoadError("project-status.json root must be an object")
    section = payload.get(R3_SECTION_KEY)
    if section is None:
        raise _R3SectionMissing("dashboard_r3 section is not established")
    if not isinstance(section, dict):
        raise _R3LoadError("dashboard_r3 must be an object")
    if set(section) - R3_SECTION_KEYS:
        raise _R3LoadError("dashboard_r3 contains undeclared fields")
    for key in R3_SECTION_KEYS:
        if key in section and not isinstance(section[key], list):
            raise _R3LoadError(f"dashboard_r3.{key} must be an array")
    return section


def _parse_line(raw: Any, field: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field} must be an object")
    _reject_undeclared_fields(raw, field, DELIVERY_LINE_KEYS)
    line_id = _require_string(raw.get("delivery_line_id"), f"{field}.delivery_line_id")
    if not SAFE_REFERENCE_PATTERN.fullmatch(line_id):
        raise ValueError(f"{field}.delivery_line_id is invalid")
    name = _require_string(raw.get("name"), f"{field}.name")
    scope_summary = _require_string(raw.get("scope_summary"), f"{field}.scope_summary")
    delivery_status = _require_string(raw.get("delivery_status"), f"{field}.delivery_status")
    if delivery_status not in DELIVERY_LINE_STATUS_VALUES:
        raise ValueError(f"{field}.delivery_status is not supported")
    for flag in ("can_enter_product_acceptance", "can_enter_controlled_trial"):
        if not isinstance(raw.get(flag), bool):
            raise ValueError(f"{field}.{flag} must be a boolean")
    return {
        "delivery_line_id": line_id,
        "name": name,
        "scope_summary": scope_summary,
        "delivery_status": delivery_status,
        "current_conclusion": _require_string(
            raw.get("current_conclusion"), f"{field}.current_conclusion"
        ),
        "current_candidate_summary": _require_string(
            raw.get("current_candidate_summary"), f"{field}.current_candidate_summary"
        ),
        "next_gate_summary": _require_string(
            raw.get("next_gate_summary"), f"{field}.next_gate_summary"
        ),
        "can_enter_product_acceptance": raw["can_enter_product_acceptance"],
        "can_enter_controlled_trial": raw["can_enter_controlled_trial"],
        "verified_at": _require_string(raw.get("verified_at"), f"{field}.verified_at"),
    }


def _parse_lines(entries: Any, warnings: list[str]) -> dict[str, dict[str, Any]]:
    lines: dict[str, dict[str, Any]] = {}
    if entries is None:
        return lines
    for index, raw in enumerate(entries):
        field = f"dashboard_r3.delivery_lines[{index}]"
        try:
            line = _parse_line(raw, field)
        except ValueError:
            warnings.append("R3_INVALID_LINE")
            continue
        if line["delivery_line_id"] in lines:
            warnings.append("R3_INVALID_LINE")
            continue
        lines[line["delivery_line_id"]] = line
    return lines


def _parse_evidence_ref(raw: Any, field: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field} must be an object")
    _reject_undeclared_fields(raw, field, EVIDENCE_REF_KEYS)
    ref_type = _require_string(raw.get("type"), f"{field}.type")
    if ref_type not in EVIDENCE_TYPE_VALUES:
        raise ValueError(f"{field}.type is not supported")
    ref_id = _require_string(raw.get("id"), f"{field}.id")
    if not SAFE_REFERENCE_PATTERN.fullmatch(ref_id):
        raise ValueError(f"{field}.id is invalid")
    return {"type": ref_type, "id": ref_id}


def _parse_fact(raw: Any, field: str, *, warnings: list[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field} must be an object")
    _reject_undeclared_fields(raw, field, DELIVERY_FACT_COMMON_KEYS | CANDIDATE_EXTRA_KEYS)
    fact_id = _require_string(raw.get("fact_id"), f"{field}.fact_id")
    if not SAFE_REFERENCE_PATTERN.fullmatch(fact_id):
        raise ValueError(f"{field}.fact_id is invalid")
    delivery_line_id = _require_string(
        raw.get("delivery_line_id"), f"{field}.delivery_line_id"
    )
    fact_type = _require_string(raw.get("fact_type"), f"{field}.fact_type")
    if fact_type not in FACT_TYPE_VALUES:
        raise ValueError(f"{field}.fact_type is not supported")
    status = _require_string(raw.get("status"), f"{field}.status")
    if status not in FACT_STATUS_VALUES:
        raise ValueError(f"{field}.status is not supported")
    owner_role = _require_string(raw.get("owner_role"), f"{field}.owner_role")
    if owner_role not in OWNER_ROLE_VALUES:
        raise ValueError(f"{field}.owner_role is not supported")
    verified_at = _require_string(raw.get("verified_at"), f"{field}.verified_at")
    summary = _require_string(raw.get("summary"), f"{field}.summary")

    refs_raw = raw.get("evidence_refs")
    if refs_raw is None:
        refs_raw = []
    if not isinstance(refs_raw, list):
        raise ValueError(f"{field}.evidence_refs must be an array")
    evidence_refs: list[dict[str, str]] = []
    for ref_index, ref_raw in enumerate(refs_raw):
        try:
            evidence_refs.append(
                _parse_evidence_ref(ref_raw, f"{field}.evidence_refs[{ref_index}]")
            )
        except ValueError:
            warnings.append("R3_INVALID_REF")

    workspaces_raw = raw.get("workspace_ids")
    if workspaces_raw is None:
        workspaces_raw = []
    if not isinstance(workspaces_raw, list):
        raise ValueError(f"{field}.workspace_ids must be an array")
    workspace_ids: list[str] = []
    for workspace_id in workspaces_raw:
        if workspace_id in WORKSPACE_ID_VALUES and workspace_id not in workspace_ids:
            workspace_ids.append(workspace_id)
        else:
            warnings.append("R3_INVALID_FACT")
    if not workspace_ids:
        raise ValueError(f"{field}.workspace_ids must contain a supported workspace")

    candidate_fields: dict[str, str | None] = {}
    if fact_type == "candidate":
        for key in CANDIDATE_CONTENT_KEYS:
            value = raw.get(key)
            candidate_fields[key] = (
                _require_string(value, f"{field}.{key}", allow_empty=True)
                if value is not None
                else None
            )
        declared = raw.get("candidate_status")
        candidate_fields["candidate_status"] = (
            declared if declared in CANDIDATE_STATUS_VALUES else None
        )
    elif any(key in raw for key in CANDIDATE_EXTRA_KEYS):
        raise ValueError(f"{field} contains candidate fields on a non-candidate fact")

    return {
        "fact_id": fact_id,
        "delivery_line_id": delivery_line_id,
        "fact_type": fact_type,
        "status": status,
        "owner_role": owner_role,
        "verified_at": verified_at,
        "summary": summary,
        "evidence_refs": evidence_refs,
        "workspace_ids": workspace_ids,
        "candidate_fields": candidate_fields,
    }


def _parse_facts(
    entries: Any, warnings: list[str], lines: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    if entries is None:
        return facts
    for index, raw in enumerate(entries):
        field = f"dashboard_r3.delivery_facts[{index}]"
        try:
            fact = _parse_fact(raw, field, warnings=warnings)
        except ValueError:
            warnings.append("R3_INVALID_FACT")
            continue
        if fact["fact_id"] in seen_ids:
            warnings.append("R3_INVALID_FACT")
            continue
        if fact["delivery_line_id"] not in lines:
            warnings.append("R3_INVALID_FACT")
            continue
        seen_ids.add(fact["fact_id"])
        facts.append(fact)
    return facts


def _parse_target(raw: Any, field: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field} must be an object")
    _reject_undeclared_fields(raw, field, EVIDENCE_TARGET_KEYS)
    target_type = _require_string(raw.get("type"), f"{field}.type")
    if target_type not in EVIDENCE_TYPE_VALUES:
        raise ValueError(f"{field}.type is not supported")
    target_id = _require_string(raw.get("id"), f"{field}.id")
    if not SAFE_REFERENCE_PATTERN.fullmatch(target_id):
        raise ValueError(f"{field}.id is invalid")
    status = _require_string(raw.get("status"), f"{field}.status")
    if status not in EVIDENCE_TARGET_STATUS_VALUES:
        raise ValueError(f"{field}.status is not supported")
    purpose = _require_string(raw.get("purpose"), f"{field}.purpose")
    if purpose not in EVIDENCE_PURPOSE_VALUES:
        raise ValueError(f"{field}.purpose is not supported")
    if target_type not in PURPOSE_TYPE_VALUES[purpose]:
        raise ValueError(f"{field}.purpose is incompatible with type")
    owner_role = _require_string(raw.get("owner_role"), f"{field}.owner_role")
    if owner_role not in OWNER_ROLE_VALUES:
        raise ValueError(f"{field}.owner_role is not supported")
    related_raw = raw.get("related_evidence_ids")
    if related_raw is None:
        related_raw = []
    if not isinstance(related_raw, list):
        raise ValueError(f"{field}.related_evidence_ids must be an array")
    related_evidence_ids: list[str] = []
    for related in related_raw:
        if (
            isinstance(related, str)
            and SAFE_REFERENCE_PATTERN.fullmatch(related)
            and related not in related_evidence_ids
        ):
            related_evidence_ids.append(related)
        else:
            raise ValueError(f"{field}.related_evidence_ids contains an invalid id")
    return {
        "type": target_type,
        "id": target_id,
        "title": _require_string(raw.get("title"), f"{field}.title"),
        "status": status,
        "purpose": purpose,
        "owner_role": owner_role,
        "verified_at": _require_string(raw.get("verified_at"), f"{field}.verified_at"),
        "safe_summary": _require_string(raw.get("safe_summary"), f"{field}.safe_summary"),
        "related_evidence_ids": related_evidence_ids,
    }


def _parse_targets(
    entries: Any, warnings: list[str]
) -> dict[tuple[str, str], dict[str, Any]]:
    targets: dict[tuple[str, str], dict[str, Any]] = {}
    if entries is None:
        return targets
    for index, raw in enumerate(entries):
        field = f"dashboard_r3.evidence_targets[{index}]"
        try:
            target = _parse_target(raw, field)
        except ValueError:
            warnings.append("R3_INVALID_TARGET")
            continue
        key = (target["type"], target["id"])
        if key in targets:
            warnings.append("R3_INVALID_TARGET")
            continue
        targets[key] = target
    return targets


def _parse_combinations(
    entries: Any,
    warnings: list[str],
    lines: dict[str, dict[str, Any]],
) -> dict[str, set[tuple[str, str, str, str]]]:
    by_line: dict[str, set[tuple[str, str, str, str]]] = {}
    if entries is None:
        return by_line
    for index, raw in enumerate(entries):
        field = f"dashboard_r3.declared_candidate_combinations[{index}]"
        if not isinstance(raw, dict):
            warnings.append("R3_INVALID_COMBINATION")
            continue
        try:
            _reject_undeclared_fields(raw, field, CANDIDATE_COMBINATION_KEYS)
            line_id = _require_string(raw.get("delivery_line_id"), f"{field}.delivery_line_id")
            combo = (
                _require_string(raw.get("backend_candidate"), f"{field}.backend_candidate"),
                _require_string(raw.get("frontend_candidate"), f"{field}.frontend_candidate"),
                _require_string(raw.get("migration_summary"), f"{field}.migration_summary"),
                _require_string(raw.get("startup_handoff_ref"), f"{field}.startup_handoff_ref"),
            )
        except ValueError:
            warnings.append("R3_INVALID_COMBINATION")
            continue
        if line_id not in lines:
            warnings.append("R3_INVALID_COMBINATION")
            continue
        by_line.setdefault(line_id, set()).add(combo)
    return by_line


def _evidence_availability(
    target: dict[str, Any] | None,
    *,
    project_root: Path,
    cache: dict[tuple[str, str], bool],
) -> tuple[bool, str | None]:
    """受控证据目标的可查看性：已登记、追溯真实资产、有效且未过期才可用。"""
    if target is None:
        return False, "证据尚未登记"
    key = (target["type"], target["id"])
    if key not in cache:
        cache[key] = _resolve_controlled_asset(target["type"], target["id"], project_root)
    if not cache[key]:
        return False, "证据尚未登记"
    if target["status"] == "missing":
        return False, "证据暂不可查看"
    if target["status"] == "stale":
        return False, "待复核"
    if _parse_verified_at(target["verified_at"]) is None:
        return False, "核对日期待补录"
    if _verified_at_stale(target["verified_at"]):
        return False, "待复核"
    return True, None


def _project_candidate(
    fact: dict[str, Any], combos: dict[str, set[tuple[str, str, str, str]]], warnings: list[str]
) -> dict[str, Any]:
    candidate_fields = fact["candidate_fields"]
    missing_fields: list[str] = []
    provided: dict[str, str] = {}
    for key in ("backend_candidate", "frontend_candidate", "startup_handoff_ref"):
        value = candidate_fields.get(key)
        if value is None or value == "" or value == CANDIDATE_PENDING_PLACEHOLDER:
            missing_fields.append(key)
            provided[key] = ""
        else:
            provided[key] = value
    migration = candidate_fields.get("migration_summary")
    if migration is None or migration == "":
        missing_fields.append("migration_summary")
        provided["migration_summary"] = ""
    else:
        provided["migration_summary"] = migration
    declared = candidate_fields.get("candidate_status")

    conflict_sources: list[str] = []
    if missing_fields:
        candidate_status = "pending"
        warnings.append("R3_CANDIDATE_INCOMPLETE")
    else:
        combo = (
            provided["backend_candidate"],
            provided["frontend_candidate"],
            provided["migration_summary"],
            provided["startup_handoff_ref"],
        )
        matched = combo in combos.get(fact["delivery_line_id"], set())
        if declared == "fixed" and matched:
            candidate_status = "fixed"
        elif declared == "fixed":
            candidate_status = "inconsistent"
            conflict_sources.append("候选组合与已声明组合不匹配")
            warnings.append("R3_CANDIDATE_UNMATCHED")
        elif declared == "inconsistent":
            candidate_status = "inconsistent"
            conflict_sources.append("数据声明候选不一致")
            warnings.append("R3_CANDIDATE_UNMATCHED")
        else:
            candidate_status = "inconsistent"
            conflict_sources.append("candidate_status 声明与已提供候选字段冲突")
            warnings.append("R3_CANDIDATE_STATUS_MISMATCH")

    return {
        "backend_candidate": provided["backend_candidate"],
        "frontend_candidate": provided["frontend_candidate"],
        "migration_summary": provided["migration_summary"],
        "startup_handoff_ref": provided["startup_handoff_ref"],
        "candidate_status": candidate_status,
        "candidate_status_label": CANDIDATE_STATUS_LABELS[candidate_status],
        "missing_fields": missing_fields,
        "conflict_sources": conflict_sources,
    }


def _project_fact(
    fact: dict[str, Any],
    lines: dict[str, dict[str, Any]],
    targets: dict[tuple[str, str], dict[str, Any]],
    combos: dict[str, set[tuple[str, str, str, str]]],
    warnings: list[str],
    *,
    project_root: Path,
    cache: dict[tuple[str, str], bool],
) -> dict[str, Any]:
    projected: dict[str, Any] = {
        "fact_id": fact["fact_id"],
        "delivery_line_id": fact["delivery_line_id"],
        "delivery_line_label": lines[fact["delivery_line_id"]]["name"],
        "fact_type": fact["fact_type"],
        "status": fact["status"],
        "owner_role": fact["owner_role"],
        "owner_role_label": OWNER_ROLE_LABELS[fact["owner_role"]],
        "verified_at": fact["verified_at"],
        "summary": fact["summary"],
        "evidence_refs": list(fact["evidence_refs"]),
        "workspace_ids": list(fact["workspace_ids"]),
    }

    candidate_status: str | None = None
    if fact["fact_type"] == "candidate":
        candidate = _project_candidate(fact, combos, warnings)
        projected.update(candidate)
        candidate_status = candidate["candidate_status"]
        if candidate_status == "inconsistent":
            projected["summary"] = INCONSISTENT_SAFE_SUMMARY
        if candidate_status in ("pending", "inconsistent"):
            # 候选未固定或冲突时，事实不得保持 verified 可信状态。
            projected["status"] = "pending_check"

    stale_flag = _verified_at_stale(fact["verified_at"])
    if stale_flag is None:
        warnings.append("R3_FACT_VERIFIED_AT_MISSING")

    needs_evidence = fact["fact_type"] == "completed" or (
        fact["fact_type"] == "candidate" and candidate_status == "fixed"
    )
    if needs_evidence:
        availabilities = [
            _evidence_availability(
                targets.get((ref["type"], ref["id"])),
                project_root=project_root,
                cache=cache,
            )
            for ref in fact["evidence_refs"]
        ]
        has_valid = any(available for available, _ in availabilities)
        if not has_valid:
            if any(reason == "待复核" for _, reason in availabilities):
                projected["status"] = "stale"
                warnings.append("R3_FACT_STALE")
            else:
                projected["status"] = "pending_check"
                warnings.append("R3_FACT_EVIDENCE_MISSING")

    if stale_flag is True and projected["status"] == fact["status"]:
        projected["status"] = "stale"
        warnings.append("R3_FACT_STALE")
    return projected


def _project_line(
    line: dict[str, Any],
    facts_by_line: dict[str, list[dict[str, Any]]],
    targets: dict[tuple[str, str], dict[str, Any]],
    warnings: list[str],
    *,
    project_root: Path,
    cache: dict[tuple[str, str], bool],
) -> dict[str, Any]:
    flags = {
        "can_enter_product_acceptance": line["can_enter_product_acceptance"],
        "can_enter_controlled_trial": line["can_enter_controlled_trial"],
    }
    line_facts = facts_by_line.get(line["delivery_line_id"], [])
    line_evidence: list[tuple[str, str]] = []
    for fact in line_facts:
        for ref in fact["evidence_refs"]:
            key = (ref["type"], ref["id"])
            if key not in line_evidence:
                line_evidence.append(key)
    available_evidence: list[dict[str, str]] = []
    for ref_type, ref_id in line_evidence:
        if _evidence_availability(
            targets.get((ref_type, ref_id)),
            project_root=project_root,
            cache=cache,
        )[0]:
            available_evidence.append({"type": ref_type, "id": ref_id})
    available_purposes = {
        targets[(item["type"], item["id"])]["purpose"]
        for item in available_evidence
    }
    has_independent_test = "independent_test" in available_purposes
    has_product_acceptance = "product_acceptance" in available_purposes
    has_p8_min_runtime = "p8_min_runtime" in available_purposes
    if any(
        fact.get("candidate_status") == "inconsistent"
        for fact in line_facts
        if fact["fact_type"] == "candidate"
    ):
        flags["can_enter_product_acceptance"] = False
        flags["can_enter_controlled_trial"] = False
        warnings.append("R3_LINE_CANDIDATE_INCONSISTENT")
    if line["can_enter_product_acceptance"] and not (
        has_independent_test or has_p8_min_runtime
    ):
        flags["can_enter_product_acceptance"] = False
        warnings.append("R3_LINE_FLAG_UNVERIFIED")
    # DASH-LITE-003：可试用必须同时具备产品人工验收结论与 P8-min 运行证据。
    if line["can_enter_controlled_trial"] and not (
        has_p8_min_runtime and has_product_acceptance
    ):
        flags["can_enter_controlled_trial"] = False
        warnings.append("R3_LINE_TRIAL_UNVERIFIED")
    if line["delivery_status"] == "ready_for_trial" and not (
        has_p8_min_runtime and has_product_acceptance
    ):
        flags["can_enter_product_acceptance"] = False
        flags["can_enter_controlled_trial"] = False
        warnings.append("R3_LINE_TRIAL_UNVERIFIED")
    line_stale = _verified_at_stale(line["verified_at"])
    if line_stale is None:
        warnings.append("R3_LINE_VERIFIED_AT_MISSING")
    elif line_stale:
        warnings.append("R3_LINE_STALE")
    return {
        "delivery_line_id": line["delivery_line_id"],
        "name": line["name"],
        "scope_summary": line["scope_summary"],
        "delivery_status": line["delivery_status"],
        "delivery_status_label": DELIVERY_STATUS_LABELS[line["delivery_status"]],
        "current_conclusion": line["current_conclusion"],
        "current_candidate_summary": line["current_candidate_summary"],
        "next_gate_summary": line["next_gate_summary"],
        "can_enter_product_acceptance": flags["can_enter_product_acceptance"],
        "can_enter_controlled_trial": flags["can_enter_controlled_trial"],
        "verified_at": line["verified_at"],
    }


def _project_evidence(
    ref_type: str,
    ref_id: str,
    targets: dict[tuple[str, str], dict[str, Any]],
    *,
    project_root: Path,
    cache: dict[tuple[str, str], bool],
) -> dict[str, Any]:
    target = targets.get((ref_type, ref_id))
    available, reason = _evidence_availability(
        target, project_root=project_root, cache=cache
    )
    if target is None:
        return {
            "type": ref_type,
            "id": ref_id,
            "title": None,
            "status": None,
            "owner_role": None,
            "owner_role_label": None,
            "verified_at": None,
            "safe_summary": None,
            "available": False,
            "unavailable_reason": reason,
        }
    return {
        "type": target["type"],
        "id": target["id"],
        "title": target["title"],
        "status": target["status"],
        "owner_role": target["owner_role"],
        "owner_role_label": OWNER_ROLE_LABELS[target["owner_role"]],
        "verified_at": target["verified_at"],
        "safe_summary": target["safe_summary"],
        "available": available,
        "unavailable_reason": reason,
    }


def _empty_workspace_view(workspace_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workspace": {"id": workspace_id, "label": WORKSPACE_LABELS[workspace_id]},
        "line_options": [],
        "selected_line": None,
        "cards": {
            "conclusion": {"items": []},
            "progress": {"facts": []},
            "gates_and_blockers": {"facts": []},
            "checked_evidence": {"items": []},
        },
        "warnings": [],
    }


def build_r3_workspace_view(
    workspace_id: str,
    *,
    line_id: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """构造 R3 工作区受控投影；任何根级数据失败都返回安全空投影。"""
    if workspace_id not in WORKSPACE_ID_VALUES:
        raise KeyError(workspace_id)
    view = _empty_workspace_view(workspace_id)
    try:
        section = _load_r3_section(project_root)
    except _R3SectionMissing:
        view["warnings"].append(_warning("R3_SECTION_MISSING"))
        return view
    except _R3LoadError:
        view["warnings"].append(_warning("R3_DATA_UNAVAILABLE"))
        return view

    warnings: list[str] = []
    lines = _parse_lines(section.get("delivery_lines"), warnings)
    targets = _parse_targets(section.get("evidence_targets"), warnings)
    combos = _parse_combinations(
        section.get("declared_candidate_combinations"), warnings, lines
    )
    facts = _parse_facts(section.get("delivery_facts"), warnings, lines)

    view["line_options"] = [
        {"id": line_id_key, "label": line["name"]} for line_id_key, line in lines.items()
    ]
    if line_id is not None:
        if line_id not in lines:
            raise KeyError(line_id)
        view["selected_line"] = {"id": line_id, "label": lines[line_id]["name"]}

    cache: dict[tuple[str, str], bool] = {}
    projected_facts = [
        _project_fact(
            fact, lines, targets, combos, warnings, project_root=project_root, cache=cache
        )
        for fact in facts
    ]
    facts_by_line: dict[str, list[dict[str, Any]]] = {}
    for fact in projected_facts:
        facts_by_line.setdefault(fact["delivery_line_id"], []).append(fact)

    workspace_facts = [
        fact for fact in projected_facts if workspace_id in fact["workspace_ids"]
    ]
    if line_id is not None:
        selected_facts = [
            fact for fact in workspace_facts if fact["delivery_line_id"] == line_id
        ]
        if not selected_facts:
            warnings.append("R3_LINE_NO_FACTS")
        conclusion_items = [
            _project_line(
                lines[line_id],
                facts_by_line,
                targets,
                warnings,
                project_root=project_root,
                cache=cache,
            )
        ]
    else:
        selected_facts = workspace_facts
        related_line_ids = {fact["delivery_line_id"] for fact in workspace_facts}
        conclusion_items = [
            _project_line(
                lines[line_id_key],
                facts_by_line,
                targets,
                warnings,
                project_root=project_root,
                cache=cache,
            )
            for line_id_key in lines
            if line_id_key in related_line_ids
        ]

    seen_evidence: set[tuple[str, str]] = set()
    evidence_items: list[dict[str, Any]] = []
    for fact in selected_facts:
        for ref in fact["evidence_refs"]:
            key = (ref["type"], ref["id"])
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            evidence_items.append(
                _project_evidence(
                    ref["type"], ref["id"], targets, project_root=project_root, cache=cache
                )
            )

    view["cards"] = {
        "conclusion": {"items": conclusion_items},
        "progress": {
            "facts": [fact for fact in selected_facts if fact["fact_type"] in PROGRESS_FACT_TYPES]
        },
        "gates_and_blockers": {
            "facts": [fact for fact in selected_facts if fact["fact_type"] in GATE_FACT_TYPES]
        },
        "checked_evidence": {"items": evidence_items},
    }
    view["warnings"] = [_warning(code) for code in dict.fromkeys(warnings)]
    return view


def load_r3_evidence_detail(
    evidence_type: str, evidence_id: str, *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """仅按受控 evidence_targets 注册表返回安全详情；其余情况一律 KeyError。"""
    if evidence_type not in EVIDENCE_TYPE_VALUES:
        raise KeyError(evidence_type)
    try:
        section = _load_r3_section(project_root)
    except _R3LoadError as exc:
        raise KeyError((evidence_type, evidence_id)) from exc
    targets = _parse_targets(section.get("evidence_targets"), [])
    target = targets.get((evidence_type, evidence_id))
    if target is None:
        raise KeyError((evidence_type, evidence_id))
    available, reason = _evidence_availability(
        target, project_root=project_root, cache={}
    )
    return {
        "type": target["type"],
        "id": target["id"],
        "title": target["title"],
        "status": target["status"],
        "owner_role": target["owner_role"],
        "owner_role_label": OWNER_ROLE_LABELS[target["owner_role"]],
        "verified_at": target["verified_at"],
        "safe_summary": target["safe_summary"],
        "related_evidence_ids": list(target["related_evidence_ids"]),
        "available": available,
        "unavailable_reason": reason,
    }
