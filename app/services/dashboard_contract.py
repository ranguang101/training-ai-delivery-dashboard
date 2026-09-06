"""Shared status catalog and safe compatibility checks for the dashboard.

The dashboard is a local, read-only projection.  Unknown source states therefore
degrade to ``pending_check`` with a field-level warning; they are never rendered
as a successful state and never make the whole page fail.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DELIVERY_STATUS_LABELS = {
    "planning": "规划中",
    "contract_freeze": "契约待冻结",
    "implementation": "实施中",
    "integration": "联调中",
    "independent_test": "独立测试中",
    "product_acceptance": "产品验收中",
    "ready_for_trial": "可试用",
}
EVIDENCE_LEVEL_LABELS = {f"D{level}": label for level, label in enumerate((
    "尚未形成受控证据",
    "产品基线证据",
    "技术方案与契约证据",
    "候选组合证据",
    "测试执行证据",
    "独立测试证据",
    "产品确认与运行门槛证据",
))}
CONTRACT_STATUS_LABELS = {
    "not_frozen": "待冻结",
    "frozen": "已冻结",
    "retest_required": "需重新验证",
    "not_applicable": "不适用",
}
CANDIDATE_VERSION_STATUS_LABELS = {
    "not_fixed": "候选待组合",
    "fixed": "候选组合已固定",
    "superseded": "候选已替代",
}
RUNTIME_GATE_STATUS_LABELS = {
    "not_assessed": "待核对",
    "open": "待处理",
    "blocked": "已阻断",
    "evidence_ready": "证据已具备",
    "passed": "运行门槛通过",
}
SOURCE_ROLE_LABELS = {
    "product": "产品负责人",
    "development": "服务端技术负责人",
    "testing": "测试负责人",
    "project_owner": "项目负责人",
}
ROLE_STATUS_LABELS = {
    "not_started": "未开始",
    "planned": "未开始",
    "preparing": "准备中",
    "pending": "待确认",
    "in_progress": "进行中",
    "blocked": "已阻断",
    "completed": "已完成",
    "product_acceptance_passed": "产品验收已通过",
}
QUALITY_REQUIREMENT_STATUS_LABELS = {
    "not_started": "未开始",
    "designing": "测试设计中",
    "executing": "测试执行中",
    "blocked": "测试受阻",
    "report_pending": "待出具测试报告",
    "ready_for_product_acceptance": "可进入产品验收",
    "archived": "已归档",
}
QUALITY_CANDIDATE_STATUS_LABELS = {
    "pending": "候选信息待补齐",
    "fixed": "候选组合已固定",
    "inconsistent": "候选不一致，状态待核对",
}
TEST_CASE_STATUS_LABELS = {
    "passed": "通过",
    "failed": "未通过",
    "not_executed": "未执行",
    "pending_review": "待确认",
    "blocked": "阻塞",
}
TEST_RUN_STATUS_LABELS = {
    "not_executed": "未执行",
    "passed": "通过",
    "failed": "失败",
    "blocked": "阻塞",
    "not_applicable": "不适用",
}
AUTOMATION_STATUS_LABELS = {
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
RETEST_STATUS_LABELS = {
    "not_required": "无需复测",
    "pending": "待复测",
    "passed": "复测通过",
    "failed": "复测失败",
    "partial": "部分复测",
}
TEST_REPORT_STATUS_LABELS = {
    "not_available": "尚未形成",
    "draft": "草稿",
    "passed": "通过",
    "failed": "失败",
    "blocked": "阻塞",
}

STATUS_CATALOG: Mapping[str, Mapping[str, str]] = {
    "delivery_status": DELIVERY_STATUS_LABELS,
    "evidence_level": EVIDENCE_LEVEL_LABELS,
    "contract_state.status": CONTRACT_STATUS_LABELS,
    "candidate_version.status": CANDIDATE_VERSION_STATUS_LABELS,
    "runtime_gate.status": RUNTIME_GATE_STATUS_LABELS,
    "source_role": SOURCE_ROLE_LABELS,
    "role.status": ROLE_STATUS_LABELS,
    "quality_requirement.status": QUALITY_REQUIREMENT_STATUS_LABELS,
    "quality_candidate.status": QUALITY_CANDIDATE_STATUS_LABELS,
    "test_case.status": TEST_CASE_STATUS_LABELS,
    "test_run.status": TEST_RUN_STATUS_LABELS,
    "automation.status": AUTOMATION_STATUS_LABELS,
    "defect.status": DEFECT_STATUS_LABELS,
    "retest.status": RETEST_STATUS_LABELS,
    "test_report.status": TEST_REPORT_STATUS_LABELS,
}

# Kept independently from labels so tests detect a missing or accidental display mapping.
STATUS_VALUES: Mapping[str, frozenset[str]] = {
    "delivery_status": frozenset({
        "planning", "contract_freeze", "implementation", "integration",
        "independent_test", "product_acceptance", "ready_for_trial",
    }),
    "evidence_level": frozenset({"D0", "D1", "D2", "D3", "D4", "D5", "D6"}),
    "contract_state.status": frozenset({
        "not_frozen", "frozen", "retest_required", "not_applicable"
    }),
    "candidate_version.status": frozenset({"not_fixed", "fixed", "superseded"}),
    "runtime_gate.status": frozenset({
        "not_assessed", "open", "blocked", "evidence_ready", "passed"
    }),
    "source_role": frozenset({"product", "development", "testing", "project_owner"}),
    "role.status": frozenset({
        "not_started", "planned", "preparing", "pending", "in_progress", "blocked",
        "completed", "product_acceptance_passed",
    }),
    "quality_requirement.status": frozenset({
        "not_started", "designing", "executing", "blocked", "report_pending",
        "ready_for_product_acceptance", "archived",
    }),
    "quality_candidate.status": frozenset({"pending", "fixed", "inconsistent"}),
    "test_case.status": frozenset({
        "passed", "failed", "not_executed", "pending_review", "blocked"
    }),
    "test_run.status": frozenset({
        "not_executed", "passed", "failed", "blocked", "not_applicable"
    }),
    "automation.status": frozenset({
        "not_configured", "planned", "running", "passed_pending_human", "failed",
        "reviewed",
    }),
    "defect.status": frozenset({
        "open", "confirmed", "in_progress", "ready_for_retest", "retest_partial",
        "retest_failed", "closed", "retest_passed",
    }),
    "retest.status": frozenset({"not_required", "pending", "passed", "failed", "partial"}),
    "test_report.status": frozenset({"not_available", "draft", "passed", "failed", "blocked"}),
}

DELIVERY_STATUS_VALUES = STATUS_VALUES["delivery_status"]
EVIDENCE_LEVEL_VALUES = STATUS_VALUES["evidence_level"]
CONTRACT_STATUS_VALUES = STATUS_VALUES["contract_state.status"]
CANDIDATE_VERSION_STATUS_VALUES = STATUS_VALUES["candidate_version.status"]
RUNTIME_GATE_STATUS_VALUES = STATUS_VALUES["runtime_gate.status"]
SOURCE_ROLE_VALUES = STATUS_VALUES["source_role"]
ROLE_STATUS_VALUES = STATUS_VALUES["role.status"]
QUALITY_REQUIREMENT_STATUS_VALUES = STATUS_VALUES["quality_requirement.status"]
QUALITY_CANDIDATE_STATUS_VALUES = STATUS_VALUES["quality_candidate.status"]
TEST_CASE_STATUS_VALUES = STATUS_VALUES["test_case.status"]
TEST_RUN_STATUS_VALUES = STATUS_VALUES["test_run.status"]
AUTOMATION_STATUS_VALUES = STATUS_VALUES["automation.status"]
DEFECT_STATUS_VALUES = STATUS_VALUES["defect.status"]
RETEST_STATUS_VALUES = STATUS_VALUES["retest.status"]
TEST_REPORT_STATUS_VALUES = STATUS_VALUES["test_report.status"]

PENDING_STATUS = {"code": "pending_check", "label": "待核对"}


def safe_status(
    value: Any, *, field: str, labels: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, str] | None]:
    """Project one status or return a non-successful, field-addressed fallback."""
    if isinstance(value, str) and value in labels:
        return {"code": value, "label": labels[value]}, None
    return dict(PENDING_STATUS), {
        "code": "DASHBOARD_UNKNOWN_ENUM",
        "field": field,
        "safe_message": f"{field} 状态待核对",
    }


def delivery_line_relation_warnings(raw: Mapping[str, Any], *, field: str) -> list[dict[str, str]]:
    """Validate progressive evidence gates without inferring missing evidence."""
    level = raw.get("evidence_level")
    if level not in EVIDENCE_LEVEL_LABELS:
        return []  # The enum warning already gives the precise failure.

    rank = int(level[1:])
    contract = raw.get("contract_state") if isinstance(raw.get("contract_state"), dict) else {}
    candidate = (
        raw.get("candidate_version")
        if isinstance(raw.get("candidate_version"), dict)
        else {}
    )
    runtime = raw.get("runtime_gate") if isinstance(raw.get("runtime_gate"), dict) else {}
    blockers = raw.get("open_blockers") if isinstance(raw.get("open_blockers"), list) else []
    evidence = raw.get("evidence_links") if isinstance(raw.get("evidence_links"), list) else []
    evidence_levels = {
        item.get("evidence_level")
        for item in evidence
        if isinstance(item, dict) and item.get("status") not in {"missing", "conflict", "stale"}
    }

    reasons: list[str] = []
    if any(
        item_level in EVIDENCE_LEVEL_LABELS and int(item_level[1:]) > rank
        for item_level in evidence_levels
    ):
        reasons.append("证据项等级不得高于交付线等级")
    if rank >= 3 and candidate.get("status") != "fixed":
        reasons.append("固定候选")
    if rank >= 5:
        if contract.get("status") != "frozen":
            reasons.append("冻结契约")
        if runtime.get("status") not in {"evidence_ready", "passed"}:
            reasons.append("运行证据")
        if not ({"D5", "D6"} & evidence_levels):
            reasons.append("D5/D6 测试证据")
        if blockers:
            reasons.append("开放阻断清零")
    if rank >= 6:
        if runtime.get("status") != "passed":
            reasons.append("运行门槛通过")
        has_product_confirmation = any(
            isinstance(item, dict)
            and item.get("evidence_level") == "D6"
            and item.get("kind") in {"document", "handoff"}
            and item.get("source_role") in {"product", "project_owner"}
            and item.get("status") not in {"missing", "conflict", "stale"}
            for item in evidence
        )
        if not has_product_confirmation:
            reasons.append("D6 产品确认")

    if not reasons:
        return []
    return [{
        "code": "DASHBOARD_EVIDENCE_RELATION_INVALID",
        "field": field,
        "safe_message": f"{field} 缺少：{'、'.join(dict.fromkeys(reasons))}，状态待核对",
    }]
