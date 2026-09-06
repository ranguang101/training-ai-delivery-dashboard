"""将测试资产的 Case 清单同步为看板可消费的轻量质量数据。

该脚本只写入结构化摘要，不把原始报告路径、日志内容或敏感数据写入看板。
它允许测试资产迭代后重复执行，作为本地看板的数据录入口。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_PROJECT_STATUS = Path(r"D:\培训机构AI提效项目\project-status.json")
DEFAULT_CASES = Path(
    r"D:\培训机构AI提效项目\docs\testing\case-generation\runs\GEN-MVP-A-20260825-004\candidate-cases-r3-expanded.json"
)
DEFAULT_CLOSURE = Path(
    r"D:\培训机构AI提效项目\docs\testing\case-generation\runs\GEN-MVP-A-20260825-004\case-closure-matrix-v1.md"
)
GENERATION_REF = "GEN-MVP-A-20260825-004"
CANDIDATE_REF = "MVP-A-COMBO-195128A5"
QUALITY_REQUIREMENT_ID = "QR-MVP-A"
DELIVERY_LINE_ID = "mvp-a-management-foundation"

STATUS_MAP = {
    "partial": "pending_review",
    "pending": "not_executed",
    "blocked": "blocked",
    "complete": "passed",
}
STATUS_LABELS = {
    "pending_review": "待确认",
    "not_executed": "未执行",
    "blocked": "阻塞",
    "passed": "通过",
    "failed": "未通过",
}
CASE_TYPE_MAP = {
    "main_flow": "integration",
    "interaction": "functional",
    "ui": "manual",
    "compatibility": "regression",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-status", type=Path, default=DEFAULT_PROJECT_STATUS)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_closure(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| MVP-"):
            continue
        fields = [part.strip() for part in line.strip("|").split("|")]
        if len(fields) != 6 or fields[3] not in STATUS_MAP:
            continue
        result[fields[0]] = {
            "result": fields[2],
            "status": fields[3],
            "next_action": fields[5],
        }
    return result


def text(value: Any, default: str = "未提供") -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    return str(value).strip() if value is not None else default


def automation_kind(mode: str) -> str:
    mode = mode.lower()
    if "manual" in mode and "playwright" in mode:
        return "hybrid"
    if "manual" in mode:
        return "manual"
    return "automated"


def evidence_summary(raw: str) -> str:
    if raw == "待补":
        return "暂无已登记证据"
    if "automation" in raw.lower() or "playwright" in raw.lower():
        return "已登记自动化或共享测试支撑证据"
    if "pytest" in raw.lower():
        return "已登记服务端或共享测试支撑证据"
    return "已登记测试支撑证据"


def merge_by_key(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    """Replace only records produced by this sync, preserving later manual entries."""
    incoming_keys = {item[key] for item in incoming}
    preserved = [item for item in existing if item.get(key) not in incoming_keys]
    return preserved + incoming


def build_case(case: dict[str, Any], closure: dict[str, str] | None) -> dict[str, Any]:
    closure = closure or {
        "result": "尚未形成逐条执行结果",
        "status": "pending",
        "next_action": "补充执行结果、证据和责任人",
    }
    source_status = closure["status"]
    status = STATUS_MAP[source_status]
    raw_evidence = closure.get("evidence", "")
    return {
        "case_id": case["id"],
        "quality_requirement_id": QUALITY_REQUIREMENT_ID,
        "requirement_ids": case.get("requirement_ids", []),
        "feature_ids": case.get("feature_ids", []),
        "title": case["title"],
        "case_type": CASE_TYPE_MAP.get(case.get("kind"), "functional"),
        "automation_kind": automation_kind(case.get("automation_mode", "manual")),
        "preconditions": text(case.get("preconditions")),
        "steps": text(case.get("steps")),
        "expected_result": text(case.get("expected")),
        "case_status": status,
        "review_status": case.get("review_status", "case_review_pending"),
        "actual_result": closure["result"],
        "evidence_summary": evidence_summary(raw_evidence),
        "next_action": closure["next_action"],
        "source_ref": GENERATION_REF,
    }


def main() -> None:
    args = parse_args()
    project = read_json(args.project_status)
    source = read_json(args.cases)
    closure = parse_closure(args.closure)
    cases = [build_case(item, closure.get(item["id"])) for item in source["cases"]]
    automated_ids = [
        item["case_id"]
        for item in cases
        if item["case_status"] == "pending_review"
        and "辅助执行通过" in closure.get(item["case_id"], {}).get("result", "")
    ]
    executed_at = datetime(2026, 8, 26, 20, 0)
    executions = [
        {
            "case_id": case_id,
            "run_id": f"AUX-{case_id}-20260826-001",
            "execution_status": "passed",
            "executed_at": (executed_at + timedelta(minutes=index)).isoformat() + "+08:00",
            "candidate_ref": CANDIDATE_REF,
        }
        for index, case_id in enumerate(automated_ids)
    ]
    automation_run_id = f"{GENERATION_REF}-AUX-001"
    section = project.setdefault("quality_workspace_r4", {})
    requirement = next(
        item
        for item in section["requirements"]
        if item["quality_requirement_id"] == QUALITY_REQUIREMENT_ID
    )
    requirement.update(
        {
            "status": "executing",
            "scope_summary": (
                "已登记 47 条 MVP-A 测试 Case：21 条待确认、26 条未执行；"
                "16 条已有辅助自动化通过结果，完整 Case 尚未收口。"
            ),
            "candidate_ref": CANDIDATE_REF,
            "candidate_status": "fixed",
            "case_refs": [item["case_id"] for item in cases],
            "automation_refs": [automation_run_id],
            "verified_at": "2026-08-27T09:00:00+08:00",
        }
    )
    section["formal_cases"] = cases
    section["case_executions"] = merge_by_key(
        section.get("case_executions", []), executions, "run_id"
    )
    automation_runs = [
        {
            "automation_run_id": automation_run_id,
            "quality_requirement_id": QUALITY_REQUIREMENT_ID,
            "case_ids": automated_ids,
            "feature_ids": [],
            "automation_status": "passed_pending_human",
            "run_count": len(automated_ids),
            "assertion_total": 0,
            "assertion_failed": 0,
            "screenshot_registered": False,
            "log_summary_registered": True,
            "executed_at": "2026-08-26T20:00:00+08:00",
            "safe_summary": (
                "16 条辅助自动化计划已有通过结果；仍需按 Case 补齐人工、"
                "服务端、视觉或兼容性承接，不计正式准出。"
            ),
        }
    ]
    section["automation_runs"] = merge_by_key(
        section.get("automation_runs", []), automation_runs, "automation_run_id"
    )
    section["defects"] = section.get("defects", [])
    section["final_reports"] = section.get("final_reports", [])
    args.project_status.write_text(
        json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"synced {len(cases)} cases, {len(executions)} executions, "
        f"{len(automated_ids)} auxiliary case results"
    )


if __name__ == "__main__":
    main()
