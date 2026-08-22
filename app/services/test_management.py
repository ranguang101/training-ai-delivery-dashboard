import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.config import PROJECT_ROOT

TESTING_DIR = PROJECT_ROOT / "docs" / "testing"
TEST_CASES_DIR = TESTING_DIR / "cases"
TEST_INTEGRATIONS_PATH = TESTING_DIR / "integrations.json"
DEFECTS_PATH = TESTING_DIR / "defects.json"
TEST_RUNS_DIR = PROJECT_ROOT / "reports" / "test-runs"
CASE_GENERATION_DIR = TESTING_DIR / "case-generation"
CASE_GENERATION_TASKS_PATH = CASE_GENERATION_DIR / "case-generation-runs.json"
TEST_AUTOMATION_RUN_INDEX_PATH = TESTING_DIR / "automation-run-index.json"
DOCUMENT_STATUS_PATH = PROJECT_ROOT / "docs" / "document-status.json"
STAGE_CODE_PATTERN = re.compile(r"^P[0-8]$")
RUN_ID_PATTERN = re.compile(r"^RUN-P[0-8]-\d{8}-\d{6}$")
DEFECT_ID_PATTERN = re.compile(r"^BUG-P[0-8]-\d{3}$")
CASE_GENERATION_TASK_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]{1,79}$")
AUTOMATION_RUN_ID_PATTERN = re.compile(r"^AUX-[A-Z0-9][A-Z0-9-]{2,77}$")
AUTOMATION_CASE_ID_PATTERN = re.compile(r"^P[0-8]-TC-\d{3}$")
AUTOMATION_CASE_VERSION_PATTERN = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
AUTOMATION_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
AUTOMATION_EVIDENCE_ID_PATTERN = re.compile(r"^AUTOMATION-[A-Z0-9_-]{3,100}$")

AUTOMATION_STATUS_LABELS = {
    "assisted_completed_pending_review": "辅助执行完成 · 待测试复核",
}
AUTOMATION_REVIEW_STATUS_LABELS = {
    "pending_testing_review": "待测试负责人复核",
}
AUTOMATION_CLEANUP_STATUS_LABELS = {
    "passed": "清理通过",
}
AUTOMATION_CLASSIFICATION_LABELS = {
    "auxiliary_ui_automation": "辅助 UI 自动化",
}
AUTOMATION_GOVERNANCE_STATEMENT = (
    "本记录仅说明辅助 UI 自动化已完成，必须由测试负责人复核；"
    "不计入正式 Case、通过统计、缺陷或版本准出。"
)
AUTOMATION_INDEX_ALLOWED_KEYS = {
    "run_id",
    "source_case_id",
    "case_version",
    "tool_commit",
    "tested_project_commit",
    "automation_status",
    "assertion_total",
    "assertion_failed",
    "manual_items_count",
    "cleanup_status",
    "executed_at",
    "review_status",
    "classification",
    "governance_statement",
    "evidence_ids",
}

CASE_DESIGN_VIEW_LABELS = {
    "business": "业务视角",
    "interface": "接口视角",
    "interaction": "交互视角",
}
CASE_DESIGN_CANDIDATE_LABELS = {
    "api": "API 候选",
    "ui": "UI 候选",
    "manual": "人工候选",
}

_COUNT_KEYS = {
    "executed",
    "passed",
    "failed",
    "blocked",
    "not_executed",
    "automation_pending",
    "deferred",
    "manual_pending",
    "blocking_pending",
}
_CASE_RESULT_STATUSES = {
    "passed",
    "failed",
    "blocked",
    "not_executed",
    "manual_pending",
    "automation_pending",
    "deferred",
}
_OPEN_DEFECT_STATUSES = {"open", "confirmed", "fixing", "fixed", "reopened"}
_BLOCKING_SEVERITIES = {"high", "critical"}


def _cases_dir(project_root: Path | None) -> Path:
    return TEST_CASES_DIR if project_root is None else project_root / "docs" / "testing" / "cases"


def _integrations_path(project_root: Path | None) -> Path:
    if project_root is None:
        return TEST_INTEGRATIONS_PATH
    return project_root / "docs" / "testing" / "integrations.json"


def _defects_path(project_root: Path | None) -> Path:
    if project_root is None:
        return DEFECTS_PATH
    return project_root / "docs" / "testing" / "defects.json"


def _runs_dir(project_root: Path | None) -> Path:
    return TEST_RUNS_DIR if project_root is None else project_root / "reports" / "test-runs"


def _case_generation_dir(project_root: Path | None) -> Path:
    if project_root is None:
        return CASE_GENERATION_DIR
    return project_root / "docs" / "testing" / "case-generation"


def _case_generation_tasks_path(project_root: Path | None) -> Path:
    if project_root is None:
        return CASE_GENERATION_TASKS_PATH
    return _case_generation_dir(project_root) / "case-generation-runs.json"


def _automation_index_path(project_root: Path | None) -> Path:
    if project_root is None:
        return TEST_AUTOMATION_RUN_INDEX_PATH
    return project_root / "docs" / "testing" / "automation-run-index.json"


def _document_status_path(project_root: Path | None) -> Path:
    if project_root is None:
        return DOCUMENT_STATUS_PATH
    return project_root / "docs" / "document-status.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def _load_json_safe(path: Path, default: Any) -> Any:
    try:
        return _load_json(path, default)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default


def _safe_text(value: Any, *, limit: int = 500) -> str:
    """Return a bounded display string, never serializing arbitrary JSON values."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _safe_number(value: Any) -> int:
    """Only allow non-negative whole numbers in the read-only summary."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _safe_text_list(value: Any, *, limit: int = 40) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _safe_text(item))][:limit]


def _safe_reference_list(value: Any, *, limit: int = 40) -> list[dict[str, str]]:
    """Keep only identifiers and titles intended for a management-page summary."""
    if not isinstance(value, list):
        return []
    references: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            title = _safe_text(item)
            if title:
                references.append({"id": "", "title": title})
        elif isinstance(item, dict):
            identifier = _safe_text(item.get("id"), limit=120)
            title = _safe_text(item.get("title") or item.get("label"))
            if identifier or title:
                references.append({"id": identifier, "title": title})
        if len(references) == limit:
            break
    return references


def _safe_project_document_link(value: Any) -> dict[str, str] | None:
    """Accept links to project documents only; never surface external asset URLs."""
    if isinstance(value, str):
        raw_href = value
        label = value
    elif isinstance(value, dict):
        raw_href = value.get("href") or value.get("path")
        label = value.get("label") or value.get("title") or raw_href
    else:
        return None

    href = _safe_text(raw_href, limit=300).replace("\\", "/")
    safe_label = _safe_text(label, limit=200)
    if not href or not safe_label or ":" in href or "?" in href or "#" in href:
        return None
    parts = [part for part in href.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    if href.startswith("docs/"):
        return {
            "label": safe_label,
            "href": "/project-status/documents/" + quote(href, safe="/"),
        }
    if href.startswith("/project-status/documents/"):
        return {"label": safe_label, "href": href}
    return None


def _safe_baseline_text(value: Any) -> str:
    """Render only source identifiers/relative paths from a task baseline."""
    if isinstance(value, str):
        return _safe_text(value, limit=240)
    if not isinstance(value, list):
        return ""
    entries: list[str] = []
    for item in value:
        candidate = item.get("path") if isinstance(item, dict) else item
        if text := _safe_text(candidate, limit=160):
            entries.append(text)
    return "；".join(entries[:4])


def _resolve_case_generation_asset(
    value: Any, *, project_root: Path | None = None
) -> Path | None:
    raw_path = _safe_text(value, limit=240).replace("\\", "/")
    if not raw_path or ":" in raw_path or raw_path.startswith("/"):
        return None
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    base = PROJECT_ROOT if project_root is None else project_root
    if raw_path.startswith("docs/"):
        return base / relative
    return _case_generation_dir(project_root) / relative


def _load_case_generation_payload(
    *, project_root: Path | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Read test-owned candidate assets with an empty, safe failure mode.

    Candidate Case assets deliberately live outside the formal `cases/` registry.
    They are a review input, so malformed or absent files must not make the
    quality workspace unavailable or alter formal Case totals.
    """
    tasks_path = _case_generation_tasks_path(project_root)
    if not tasks_path.exists():
        return [], ["尚未提供生成任务资产；当前未显示任何候选 Case 数据。"]
    try:
        payload = _load_json(tasks_path, {})
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return [], ["生成任务资产无法读取；当前未显示任何候选 Case 数据。"]
    entries = payload.get("runs") if isinstance(payload, dict) else None
    if entries is None and isinstance(payload, dict):
        entries = payload.get("tasks")
    if not isinstance(entries, list):
        return [], ["生成任务清单格式无效；当前未显示任何候选 Case 数据。"]
    return entries, []


def _load_task_asset(
    task: dict[str, Any], *, project_root: Path | None = None
) -> tuple[dict[str, Any], str | None]:
    """Optionally merge a sibling task JSON asset without allowing path escape."""
    artifacts = task.get("artifacts") if isinstance(task.get("artifacts"), dict) else {}
    asset_name = _safe_text(
        task.get("asset") or task.get("asset_path") or artifacts.get("manifest"), limit=240
    )
    if not asset_name:
        return task, None
    asset_path = _resolve_case_generation_asset(asset_name, project_root=project_root)
    if asset_path is None:
        return task, "生成任务包含不安全的详情资产路径，已忽略该任务详情。"
    try:
        asset = _load_json(asset_path, {})
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return task, "生成任务详情资产无法读取，已仅展示安全摘要。"
    if not isinstance(asset, dict):
        return task, "生成任务详情资产格式无效，已仅展示安全摘要。"
    return {**task, **asset}, None


def _load_asset_payload(value: Any, *, project_root: Path | None = None) -> dict[str, Any]:
    asset_path = _resolve_case_generation_asset(value, project_root=project_root)
    if asset_path is None:
        return {}
    try:
        payload = _load_json(asset_path, {})
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_case_design_task(
    raw_task: Any, *, project_root: Path | None = None
) -> dict[str, Any] | None:
    if not isinstance(raw_task, dict):
        return None
    task, task_warning = _load_task_asset(raw_task, project_root=project_root)
    task_id = _safe_text(task.get("id"), limit=80).upper()
    stage = _safe_text(task.get("stage"), limit=2).upper()
    if not CASE_GENERATION_TASK_ID_PATTERN.fullmatch(
        task_id
    ) or not STAGE_CODE_PATTERN.fullmatch(stage):
        return None

    baselines_raw = (
        task.get("input_baselines")
        or task.get("input_baseline")
        or task.get("input_manifest")
        or {}
    )
    baselines_raw = baselines_raw if isinstance(baselines_raw, dict) else {}
    baselines = {
        "prd": _safe_baseline_text(baselines_raw.get("prd") or task.get("prd_baseline")),
        "contract": _safe_baseline_text(
            baselines_raw.get("contract")
            or baselines_raw.get("contracts")
            or task.get("contract_baseline")
        ),
        "error_codes": _safe_baseline_text(
            baselines_raw.get("error_codes")
            or baselines_raw.get("errors")
            or baselines_raw.get("standards")
            or task.get("error_code_baseline"),
        ),
    }
    counts = task.get("counts") if isinstance(task.get("counts"), dict) else {}
    artifacts = task.get("artifacts") if isinstance(task.get("artifacts"), dict) else {}
    outputs = task.get("outputs") if isinstance(task.get("outputs"), dict) else {}
    raw_candidates = task.get("candidate_cases")
    if not isinstance(raw_candidates, dict):
        candidate_asset = _load_asset_payload(
            artifacts.get("candidate_cases") or outputs.get("candidate_cases"),
            project_root=project_root,
        )
        cases = candidate_asset.get("cases", [])
        raw_candidates = {"api": [], "ui": [], "manual": []}
        for case in cases if isinstance(cases, list) else []:
            if not isinstance(case, dict):
                continue
            case_type = _safe_text(case.get("type")).lower()
            target = "api" if "api" in case_type else "ui" if "ui" in case_type else "manual"
            raw_candidates[target].append(
                {"id": case.get("id"), "title": case.get("title")}
            )
    candidate_groups = raw_candidates if isinstance(raw_candidates, dict) else {}
    candidates: list[dict[str, Any]] = []
    for key, label in CASE_DESIGN_CANDIDATE_LABELS.items():
        values = candidate_groups.get(key, [])
        candidates.append(
            {
                "key": key,
                "label": label,
                "entries": _safe_reference_list(values),
                "count": _safe_number(
                    task.get(f"{key}_candidate_count")
                    if task.get(f"{key}_candidate_count") is not None
                    else len(values) if isinstance(values, list) else 0
                ),
            }
        )

    raw_views = task.get("three_views") or task.get("functional_points") or {}
    derived_references: list[str] = []
    if not isinstance(raw_views, dict) or not raw_views:
        feature_asset = _load_asset_payload(
            artifacts.get("feature_points") or outputs.get("feature_points"),
            project_root=project_root,
        )
        feature_points = feature_asset.get("feature_points", [])
        raw_views = {"business": [], "interface": [], "interaction": []}
        for point in feature_points if isinstance(feature_points, list) else []:
            if not isinstance(point, dict):
                continue
            candidate = {"id": point.get("id"), "title": point.get("title")}
            source_refs = point.get("source_refs")
            if isinstance(source_refs, list):
                derived_references.extend(_safe_text_list(source_refs, limit=80))
            dimensions = (
                point.get("dimensions")
                if isinstance(point.get("dimensions"), list)
                else []
            )
            if "functional" in dimensions:
                raw_views["business"].append(candidate)
            if "security_data" in dimensions:
                raw_views["interface"].append(candidate)
            if "ui_usability" in dimensions or "compatibility" in dimensions:
                raw_views["interaction"].append(candidate)
    raw_views = raw_views if isinstance(raw_views, dict) else {}
    views: list[dict[str, Any]] = []
    for key, label in CASE_DESIGN_VIEW_LABELS.items():
        values = raw_views.get(key, [])
        views.append({"key": key, "label": label, "entries": _safe_reference_list(values)})

    review_raw = task.get("human_review") or task.get("review") or {}
    review_raw = review_raw if isinstance(review_raw, dict) else {}
    dedup_raw = task.get("deduplication") or task.get("dedup") or {}
    dedup_raw = dedup_raw if isinstance(dedup_raw, dict) else {}
    manifest_links = []
    input_manifest = task.get("input_manifest") or {}
    manifest_values = (
        input_manifest.values() if isinstance(input_manifest, dict) else []
    )
    for group in manifest_values:
        manifest_links.extend(group if isinstance(group, list) else [])
    links = [
        link
        for item in (task.get("document_links") or task.get("links") or manifest_links)
        if (link := _safe_project_document_link(item)) is not None
    ][:12]

    candidate_count = _safe_number(
        task.get("candidate_case_count") or counts.get("candidate_cases")
    )
    if not candidate_count:
        candidate_count = sum(item["count"] for item in candidates)
    normalized = {
        "id": task_id,
        "stage": stage,
        "title": _safe_text(task.get("title") or task.get("name"), limit=200) or task_id,
        "status": _safe_text(task.get("status"), limit=80) or "未提供",
        "input_baselines": baselines,
        "functional_point_count": _safe_number(
            task.get("functional_point_count") or counts.get("feature_points")
        ),
        "candidate_case_count": candidate_count,
        "coverage_status": _safe_text(task.get("coverage_status"), limit=100) or (
            f"缺口 {counts.get('coverage_gaps', 0)} 项" if counts else "待核对"
        ),
        "updated_at": _safe_text(task.get("updated_at"), limit=80) or "未提供",
        "views": views,
        "requirements": _safe_reference_list(
            task.get("related_requirements")
            or task.get("requirements")
            or [ref for ref in derived_references if "-AC-" not in ref]
        ),
        "acceptance_criteria": _safe_reference_list(
            task.get("acceptance_criteria")
            or task.get("acs")
            or [ref for ref in derived_references if "-AC-" in ref]
        ),
        "priority": _safe_text(task.get("priority"), limit=80) or "按功能点逐项评审",
        "deduplication": {
            "status": _safe_text(dedup_raw.get("status"), limit=100) or "由任务资产提供去重键",
            "note": _safe_text(dedup_raw.get("note") or dedup_raw.get("summary")),
        },
        "coverage_gaps": _safe_text_list(task.get("coverage_gaps")),
        "candidates": candidates,
        "review": {
            "decision": _safe_text(
                review_raw.get("decision")
                or review_raw.get("case_review")
                or review_raw.get("status"),
                limit=200,
            )
            or "待人工评审",
            "note": _safe_text(review_raw.get("note") or review_raw.get("summary")),
        },
        "document_links": links,
        "warning": task_warning,
    }
    return normalized


def build_case_design_center(*, project_root: Path | None = None) -> dict[str, Any]:
    """Build a safe, read-only candidate Case design view for the quality workspace."""
    raw_tasks, warnings = _load_case_generation_payload(project_root=project_root)
    tasks = [
        task
        for raw in raw_tasks
        if (task := _normalize_case_design_task(raw, project_root=project_root))
    ]
    if raw_tasks and not tasks:
        warnings.append("未发现可安全展示的生成任务；请由测试侧核对任务清单字段。")
    return {"tasks": tasks, "warnings": warnings}


def load_case_design_task(task_id: str, *, project_root: Path | None = None) -> dict[str, Any]:
    normalized_id = task_id.upper()
    if not CASE_GENERATION_TASK_ID_PATTERN.fullmatch(normalized_id):
        raise KeyError(normalized_id)
    task = next(
        (
            item
            for item in build_case_design_center(project_root=project_root)["tasks"]
            if item["id"] == normalized_id
        ),
        None,
    )
    if task is None:
        raise KeyError(normalized_id)
    return task


def _safe_automation_timestamp(value: Any) -> str | None:
    """Accept an explicitly supplied ISO timestamp, never a free-form log value."""
    if value is None:
        return None
    timestamp = _safe_text(value, limit=40)
    timestamp_pattern = (
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        r"(?:\.\d{1,6})?[+-]\d{2}:\d{2}"
    )
    if not re.fullmatch(timestamp_pattern, timestamp):
        return None
    return timestamp


def _safe_automation_evidence_ids(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    evidence_ids: list[str] = []
    for item in value:
        identifier = _safe_text(item, limit=110).upper()
        if not AUTOMATION_EVIDENCE_ID_PATTERN.fullmatch(identifier):
            return None
        evidence_ids.append(identifier)
    return evidence_ids


def _normalize_automation_run(raw_run: Any) -> dict[str, Any] | None:
    """Whitelist one non-formal automation summary without exposing raw evidence."""
    if not isinstance(raw_run, dict) or set(raw_run) - AUTOMATION_INDEX_ALLOWED_KEYS:
        return None

    run_id = _safe_text(raw_run.get("run_id"), limit=80).upper()
    source_case_id = _safe_text(raw_run.get("source_case_id"), limit=20).upper()
    case_version = _safe_text(raw_run.get("case_version"), limit=20)
    tool_commit = _safe_text(raw_run.get("tool_commit"), limit=40).lower()
    tested_project_commit = _safe_text(raw_run.get("tested_project_commit"), limit=40).lower()
    automation_status = _safe_text(raw_run.get("automation_status"), limit=80)
    cleanup_status = _safe_text(raw_run.get("cleanup_status"), limit=80)
    review_status = _safe_text(raw_run.get("review_status"), limit=80)
    classification = _safe_text(raw_run.get("classification"), limit=80)
    evidence_ids = _safe_automation_evidence_ids(raw_run.get("evidence_ids"))
    executed_at = _safe_automation_timestamp(raw_run.get("executed_at"))
    assertion_total = _safe_number(raw_run.get("assertion_total"))
    assertion_failed = _safe_number(raw_run.get("assertion_failed"))
    manual_items_count = _safe_number(raw_run.get("manual_items_count"))

    if (
        not AUTOMATION_RUN_ID_PATTERN.fullmatch(run_id)
        or not AUTOMATION_CASE_ID_PATTERN.fullmatch(source_case_id)
        or not AUTOMATION_CASE_VERSION_PATTERN.fullmatch(case_version)
        or not AUTOMATION_COMMIT_PATTERN.fullmatch(tool_commit)
        or not AUTOMATION_COMMIT_PATTERN.fullmatch(tested_project_commit)
        or automation_status not in AUTOMATION_STATUS_LABELS
        or cleanup_status not in AUTOMATION_CLEANUP_STATUS_LABELS
        or review_status not in AUTOMATION_REVIEW_STATUS_LABELS
        or classification not in AUTOMATION_CLASSIFICATION_LABELS
        or evidence_ids is None
        or assertion_failed > assertion_total
    ):
        return None

    # This sentence is intentionally generated by the application.  A source
    # asset cannot replace it with a statement that could misrepresent a formal
    # Case, a release decision, or a raw report.
    if raw_run.get("governance_statement") not in {None, AUTOMATION_GOVERNANCE_STATEMENT}:
        return None

    return {
        "run_id": run_id,
        "source_case_id": source_case_id,
        "case_version": case_version,
        "tool_commit": tool_commit,
        "tested_project_commit": tested_project_commit,
        "automation_status": automation_status,
        "automation_status_label": AUTOMATION_STATUS_LABELS[automation_status],
        "assertion_total": assertion_total,
        "assertion_failed": assertion_failed,
        "manual_items_count": manual_items_count,
        "cleanup_status": cleanup_status,
        "cleanup_status_label": AUTOMATION_CLEANUP_STATUS_LABELS[cleanup_status],
        "executed_at": executed_at,
        "review_status": review_status,
        "review_status_label": AUTOMATION_REVIEW_STATUS_LABELS[review_status],
        "classification": classification,
        "classification_label": AUTOMATION_CLASSIFICATION_LABELS[classification],
        "governance_statement": AUTOMATION_GOVERNANCE_STATEMENT,
        "evidence_ids": evidence_ids,
    }


def _load_test_automation_runs(
    *, project_root: Path | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load only a project-local, declared automation-summary index.

    The management dashboard must never discover raw runner output.  Missing
    or malformed index files therefore become an empty, safe read model rather
    than a filesystem error or a fallback to formal Case results.
    """
    index_path = _automation_index_path(project_root)
    if not index_path.exists():
        return [], ["未提供辅助自动化运行摘要；当前不显示任何辅助执行结果。"]
    try:
        payload = _load_json(index_path, {})
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return [], ["辅助自动化运行摘要无法读取；当前不显示任何辅助执行结果。"]
    runs = payload.get("runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        return [], ["辅助自动化运行摘要格式无效；当前不显示任何辅助执行结果。"]

    normalized_runs = [
        normalized for raw_run in runs if (normalized := _normalize_automation_run(raw_run))
    ]
    warnings: list[str] = []
    if len(normalized_runs) != len(runs):
        warnings.append("存在不符合受控摘要格式的条目，已不对外展示。")
    return normalized_runs, warnings


def _automation_evidence_view(run: dict[str, Any], evidence_id: str) -> dict[str, str]:
    """Map an approved identifier to a generated safe summary, never a path."""
    if evidence_id not in run["evidence_ids"]:
        raise KeyError(evidence_id)
    return {
        "id": evidence_id,
        "kind": "controlled_summary",
        "label": "受控辅助自动化摘要",
        "safe_summary": (
            f"{run['source_case_id']}：{run['assertion_total']} 项断言，"
            f"{run['assertion_failed']} 项失败；"
            "原始报告、截图和运行器输出不在管理面板展示。"
        ),
    }


def _automation_run_links(run: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            **_automation_evidence_view(run, evidence_id),
            "href": (
                "/api/v1/project-status/test-automation/runs/"
                f"{quote(run['run_id'], safe='')}/evidence/{quote(evidence_id, safe='')}"
            ),
        }
        for evidence_id in run["evidence_ids"]
    ]


def _automation_run_list_view(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "source_case_id": run["source_case_id"],
        "case_version": run["case_version"],
        "automation_status": run["automation_status"],
        "automation_status_label": run["automation_status_label"],
        "assertion_total": run["assertion_total"],
        "assertion_failed": run["assertion_failed"],
        "manual_items_count": run["manual_items_count"],
        "cleanup_status": run["cleanup_status"],
        "cleanup_status_label": run["cleanup_status_label"],
        "executed_at": run["executed_at"],
        "review_status": run["review_status"],
        "review_status_label": run["review_status_label"],
        "classification": run["classification"],
        "classification_label": run["classification_label"],
        "governance_statement": run["governance_statement"],
        "detail_href": (
            "/api/v1/project-status/test-automation/runs/"
            f"{quote(run['run_id'], safe='')}"
        ),
    }


def build_test_automation_center(*, project_root: Path | None = None) -> dict[str, Any]:
    """Return a formal-statistics-independent read model for auxiliary runs."""
    runs, warnings = _load_test_automation_runs(project_root=project_root)
    return {
        "governance_statement": AUTOMATION_GOVERNANCE_STATEMENT,
        "summary": {
            "listed_runs": len(runs),
            "formal_case_statistics_changed": False,
            "release_decision_changed": False,
        },
        "runs": [_automation_run_list_view(run) for run in runs],
        "warnings": warnings,
    }


def load_test_automation_run(run_id: str, *, project_root: Path | None = None) -> dict[str, Any]:
    """Return one safe detail record from the declared local index."""
    normalized_id = run_id.upper()
    if not AUTOMATION_RUN_ID_PATTERN.fullmatch(normalized_id):
        raise KeyError(normalized_id)
    runs, _ = _load_test_automation_runs(project_root=project_root)
    run = next((item for item in runs if item["run_id"] == normalized_id), None)
    if run is None:
        raise KeyError(normalized_id)
    return {**run, "evidence_links": _automation_run_links(run)}


def load_test_automation_evidence(
    run_id: str, evidence_id: str, *, project_root: Path | None = None
) -> dict[str, str]:
    run = load_test_automation_run(run_id, project_root=project_root)
    normalized_evidence_id = evidence_id.upper()
    if not AUTOMATION_EVIDENCE_ID_PATTERN.fullmatch(normalized_evidence_id):
        raise KeyError(normalized_evidence_id)
    return _automation_evidence_view(run, normalized_evidence_id)


def normalize_stage_code(stage_code: str) -> str:
    normalized = stage_code.upper()
    if not STAGE_CODE_PATTERN.fullmatch(normalized):
        raise KeyError(normalized)
    return normalized


def load_test_cases(stage_code: str, *, project_root: Path | None = None) -> list[dict[str, Any]]:
    normalized = normalize_stage_code(stage_code)
    cases_dir = _cases_dir(project_root)
    payload = _load_json(cases_dir / f"{normalized}.json", {"cases": []})
    if not isinstance(payload, dict) or not isinstance(payload.get("cases", []), list):
        raise ValueError(f"Invalid test case registry for {normalized}")
    return payload["cases"]


def load_test_integrations(*, project_root: Path | None = None) -> list[dict[str, Any]]:
    """A corrupt integration list degrades to empty, never breaks the page."""
    payload = _load_json_safe(
        _integrations_path(project_root), {"items": []}
    )
    if not isinstance(payload, dict):
        return []
    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def load_defects(
    stage_code: str | None = None, *, project_root: Path | None = None
) -> list[dict[str, Any]]:
    """A corrupt defect list degrades to empty, never breaks the page."""
    payload = _load_json_safe(_defects_path(project_root), {"defects": []})
    if not isinstance(payload, dict):
        return []
    defects = payload.get("defects", [])
    if not isinstance(defects, list):
        return []
    if stage_code is None:
        return defects
    normalized = normalize_stage_code(stage_code)
    return [item for item in defects if item.get("stage") == normalized]


def load_defect(defect_id: str, *, project_root: Path | None = None) -> dict[str, Any]:
    normalized = defect_id.upper()
    if not DEFECT_ID_PATTERN.fullmatch(normalized):
        raise KeyError(normalized)
    defect = next(
        (item for item in load_defects(project_root=project_root) if item.get("id") == normalized),
        None,
    )
    if defect is None:
        raise KeyError(normalized)
    return defect


def _is_valid_test_run(run: dict[str, Any]) -> bool:
    """A run only counts as an acceptance basis when it is well-formed and clean.

    Debug records (dirty worktree or missing commit evidence) and malformed
    count tables must never silently produce a ``passed`` stage summary.
    """
    if not isinstance(run, dict):
        return False
    if not RUN_ID_PATTERN.fullmatch(str(run.get("id", ""))):
        return False
    if run.get("git_dirty") is True:
        return False
    if run.get("code_version") == "UNCOMMITTED":
        return False
    counts = run.get("counts")
    if not isinstance(counts, dict):
        return False
    for key in _COUNT_KEYS:
        value = counts.get(key)
        if (
            value is not None
            and (isinstance(value, bool) or not isinstance(value, int) or value < 0)
        ):
            return False
    executed = counts.get("executed")
    passed = counts.get("passed")
    failed = counts.get("failed")
    blocked = counts.get("blocked")
    if (
        executed is not None
        and passed is not None
        and failed is not None
        and blocked is not None
        and executed != passed + failed + blocked
    ):
        return False
    case_results = run.get("case_results")
    if not isinstance(case_results, list):
        return False
    return all(
        isinstance(item, dict)
        and item.get("case_id")
        and item.get("status") in _CASE_RESULT_STATUSES
        for item in case_results
    )


def load_test_runs(
    stage_code: str | None = None, *, project_root: Path | None = None
) -> list[dict[str, Any]]:
    """A single corrupt summary.json must not break the whole run listing."""
    normalized = normalize_stage_code(stage_code) if stage_code else None
    runs_dir = _runs_dir(project_root)
    runs: list[dict[str, Any]] = []
    if not runs_dir.exists():
        return runs
    for summary_path in runs_dir.glob("*/summary.json"):
        summary = _load_json_safe(summary_path, None)
        if not isinstance(summary, dict):
            continue
        if normalized and summary.get("stage") != normalized:
            continue
        runs.append(summary)
    return sorted(runs, key=lambda item: item.get("started_at", ""), reverse=True)


def load_test_run(run_id: str, *, project_root: Path | None = None) -> dict[str, Any]:
    normalized = run_id.upper()
    if not RUN_ID_PATTERN.fullmatch(normalized):
        raise KeyError(normalized)
    runs_dir = _runs_dir(project_root)
    summary = _load_json(runs_dir / normalized / "summary.json", None)
    if not isinstance(summary, dict):
        raise KeyError(normalized)
    return summary


def latest_case_results(
    stage_code: str, *, project_root: Path | None = None
) -> dict[str, dict[str, Any]]:
    runs = load_test_runs(stage_code, project_root=project_root)
    latest = next((run for run in runs if _is_valid_test_run(run)), None)
    if latest is None:
        return {}
    return {
        item["case_id"]: item
        for item in latest.get("case_results", [])
        if item.get("case_id")
    }


def cases_with_latest_result(
    stage_code: str, *, project_root: Path | None = None
) -> list[dict[str, Any]]:
    results = latest_case_results(stage_code, project_root=project_root)
    enriched: list[dict[str, Any]] = []
    for case in load_test_cases(stage_code, project_root=project_root):
        item = dict(case)
        item["latest_result"] = results.get(case["id"])
        enriched.append(item)
    return enriched


def summarize_run_case_types(
    cases: list[dict[str, Any]], case_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Produce a report-friendly breakdown by Case type and execution method."""
    results_by_case = {
        item.get("case_id"): item for item in case_results if item.get("case_id")
    }
    summary_by_type: dict[str, dict[str, Any]] = {}

    for case in cases:
        case_type = case.get("type", "other")
        summary = summary_by_type.setdefault(
            case_type,
            {
                "type": case_type,
                "total": 0,
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "blocked": 0,
                "pending": 0,
                "frameworks": set(),
            },
        )
        summary["total"] += 1
        framework = case.get("automation", {}).get("framework", "manual")
        summary["frameworks"].add(framework)
        status = results_by_case.get(case["id"], {}).get("status", "not_executed")
        if status in {"passed", "failed", "blocked"}:
            summary["executed"] += 1
        if status in {"passed", "failed", "blocked"}:
            summary[status] += 1
        else:
            summary["pending"] += 1

    return [
        {**item, "frameworks": " / ".join(sorted(item["frameworks"]))}
        for item in sorted(summary_by_type.values(), key=lambda item: item["type"])
    ]


def _load_json_with_warning(
    path: Path, default: Any, warnings: list[str], label: str, expected: Any
) -> Any:
    """Load one asset and record a safe, content-free degradation notice."""
    try:
        payload = _load_json(path, default)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        warnings.append(f"{label}无法读取，已安全降级显示。")
        return default
    if payload is None:
        warnings.append(f"{label}格式无效，已安全降级显示。")
        return default
    if expected is not None and not isinstance(payload, expected):
        warnings.append(f"{label}格式无效，已安全降级显示。")
        return default
    return payload


def _asset_warning_for_stage(
    normalized: str, *, project_root: Path | None
) -> list[str]:
    warnings: list[str] = []
    cases_path = _cases_dir(project_root) / f"{normalized}.json"
    if cases_path.exists():
        payload = _load_json_with_warning(cases_path, {"cases": []}, warnings,
                                          f"{normalized} 正式 Case 清单", dict)
        if not isinstance(payload.get("cases", []), list):
            warnings.append(f"{normalized} 正式 Case 清单格式无效，已安全降级显示。")
    runs_dir = _runs_dir(project_root)
    if runs_dir.exists():
        bad_runs = 0
        for summary_path in runs_dir.glob("*/summary.json"):
            try:
                payload = _load_json(summary_path, None)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                bad_runs += 1
                continue
            if not isinstance(payload, dict):
                bad_runs += 1
                continue
            if payload.get("stage") == normalized and not _is_valid_test_run(payload):
                bad_runs += 1
        if bad_runs:
            warnings.append(f"{normalized} 存在无效或非受控的测试运行记录，已安全降级。")
    defects_path = _defects_path(project_root)
    if defects_path.exists():
        payload = _load_json_with_warning(defects_path, {"defects": []}, warnings,
                                          "缺陷清单", dict)
        if not isinstance(payload.get("defects", []), list):
            warnings.append("缺陷清单格式无效，已安全降级显示。")
    integrations_path = _integrations_path(project_root)
    if integrations_path.exists():
        payload = _load_json_with_warning(integrations_path, {"items": []}, warnings,
                                          "测试接入清单", dict)
        if not isinstance(payload.get("items", []), list):
            warnings.append("测试接入清单格式无效，已安全降级显示。")
    return warnings


def _shared_asset_warnings(*, project_root: Path | None) -> list[str]:
    warnings: list[str] = []
    doc_status = _document_status_path(project_root)
    if doc_status.exists():
        payload = _load_json_with_warning(doc_status, {}, warnings,
                                          "文档状态清单", dict)
        if not isinstance(payload.get("documents", {}), dict):
            warnings.append("文档状态清单格式无效，已安全降级显示。")
    tasks_path = _case_generation_tasks_path(project_root)
    if tasks_path.exists():
        payload = _load_json_with_warning(tasks_path, {}, warnings,
                                          "候选 Case 生成任务资产", dict)
        entries = payload.get("runs")
        if entries is None:
            entries = payload.get("tasks")
        if not isinstance(entries, list):
            warnings.append("候选 Case 生成任务资产格式无效，已安全降级显示。")
    automation_path = _automation_index_path(project_root)
    if automation_path.exists():
        payload = _load_json_with_warning(automation_path, {}, warnings,
                                          "辅助自动化运行摘要", dict)
        if not isinstance(payload.get("runs"), list):
            warnings.append("辅助自动化运行摘要格式无效，已安全降级显示。")
    return warnings


def stage_test_summary(
    stage_code: str, *, project_root: Path | None = None
) -> dict[str, Any]:
    normalized = normalize_stage_code(stage_code)
    warnings = _asset_warning_for_stage(normalized, project_root=project_root)
    try:
        cases = load_test_cases(normalized, project_root=project_root)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        cases = []
    runs = load_test_runs(normalized, project_root=project_root)
    defects = load_defects(normalized, project_root=project_root)
    latest = next((run for run in runs if _is_valid_test_run(run)), None)
    most_recent_run = runs[0] if runs else None
    most_recent_uncontrolled = (
        most_recent_run is not None and most_recent_run is not latest
    )

    automation_counts = {
        "automated": sum(item.get("automation_status") == "automated" for item in cases),
        "planned": sum(item.get("automation_status") == "planned" for item in cases),
        "manual": sum(item.get("automation_status") == "manual" for item in cases),
    }
    result_counts = (latest or {}).get(
        "counts",
        {"executed": 0, "passed": 0, "failed": 0, "blocked": 0, "not_executed": 0,
         "automation_pending": 0, "deferred": 0, "manual_pending": 0, "blocking_pending": 0},
    )
    open_defects = sum(item.get("status") not in {"closed", "retest_passed"} for item in defects)
    open_blocking_defects = sum(
        item.get("severity") in _BLOCKING_SEVERITIES
        and item.get("status") in _OPEN_DEFECT_STATUSES
        for item in defects
    )

    if not cases:
        status = "not_started"
        note = "需求规格已准备，等待对应阶段开始时建立正式测试Case。"
    elif latest is None and runs:
        status = "in_progress"
        note = "最近测试运行记录无效或包含未提交修改，不能作为验收依据，等待受控正式执行报告。"
    elif latest is None:
        status = "ready"
        note = "测试Case已经建立，等待生成第一份执行报告。"
    elif result_counts.get("failed", 0):
        status = "failed"
        note = "最近一次执行存在失败，请查看测试报告和缺陷分类。"
    elif result_counts.get("blocked", 0):
        status = "blocked"
        note = "最近一次执行存在阻塞项。"
    elif open_blocking_defects:
        status = "blocked"
        note = "存在未关闭的高/严重缺陷，阻断本阶段验收。"
    elif result_counts.get("blocking_pending", 0):
        status = "in_progress"
        note = "阻断验收的Case尚未完成。"
    elif most_recent_uncontrolled:
        status = "in_progress"
        note = "最近一次执行记录无效或含未提交修改，等待受控正式执行报告。"
    else:
        status = "passed"
        note = f"{normalized}阻断项全部通过；待自动化与阶段后置事项继续保留，但不影响本阶段验收。"

    return {
        "status": status,
        "total": len(cases),
        "executed": result_counts.get("executed", 0),
        "passed": result_counts.get("passed", 0),
        "failed": result_counts.get("failed", 0),
        "blocked": result_counts.get("blocked", 0),
        "not_executed": result_counts.get("not_executed", len(cases)),
        "automation_pending": result_counts.get("automation_pending", 0),
        "deferred": result_counts.get("deferred", 0),
        "manual_pending": result_counts.get("manual_pending", 0),
        "blocking_pending": result_counts.get("blocking_pending", 0),
        "automated": automation_counts["automated"],
        "planned": automation_counts["planned"],
        "manual": automation_counts["manual"],
        "open_defects": open_defects,
        "blocking_defects": open_blocking_defects,
        "blockers": [],
        "note": note,
        "latest_run": latest,
        "warnings": warnings,
    }


def build_test_center(
    project: dict[str, Any], *, project_root: Path | None = None
) -> dict[str, Any]:
    stages = []
    warnings: list[str] = []
    for stage in project.get("stages", []):
        testing = stage_test_summary(stage["code"], project_root=project_root)
        for warning in testing.pop("warnings", []):
            if warning not in warnings:
                warnings.append(warning)
        item = {
            "code": stage["code"],
            "title": stage["title"],
            "development_status": stage.get("development", {}).get("status", "pending"),
            "requirements_count": stage.get("requirements_count", 0),
            "testing": testing,
        }
        stages.append(item)
    for warning in _shared_asset_warnings(project_root=project_root):
        if warning not in warnings:
            warnings.append(warning)

    totals = {
        "requirements": sum(item["requirements_count"] for item in stages),
        "cases": sum(item["testing"]["total"] for item in stages),
        "automated": sum(item["testing"]["automated"] for item in stages),
        "executed": sum(item["testing"]["executed"] for item in stages),
        "passed": sum(item["testing"]["passed"] for item in stages),
        "failed": sum(item["testing"]["failed"] for item in stages),
        "open_defects": sum(item["testing"]["open_defects"] for item in stages),
    }
    return {
        "stages": stages,
        "totals": totals,
        "integrations": load_test_integrations(project_root=project_root),
        "recent_runs": load_test_runs(project_root=project_root)[:8],
        "recent_defects": load_defects(project_root=project_root)[:8],
        "warnings": warnings,
    }
