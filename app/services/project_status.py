import json
import re
from pathlib import Path
from typing import Any

import markdown

from app.config import PROJECT_ROOT
from app.services.markdown_safety import sanitize_html
from app.services.test_management import (
    _is_valid_test_run,
    load_defects,
    stage_test_summary,
)

PROJECT_STATUS_PATH = PROJECT_ROOT / "project-status.json"
REQUIREMENTS_DIR = PROJECT_ROOT / "docs" / "requirements"
STAGE_REQUIREMENTS_DIR = REQUIREMENTS_DIR / "stages"
HANDOFFS_DIR = PROJECT_ROOT / "docs" / "internal" / "handoffs"
TEST_RUNS_DIR = PROJECT_ROOT / "reports" / "test-runs"
STAGE_CODE_PATTERN = re.compile(r"^P[0-8]$")
DELIVERY_LINE_STATUS_VALUES = {
    "planning",
    "contract_freeze",
    "implementation",
    "integration",
    "independent_test",
    "product_acceptance",
    "ready_for_trial",
}
CONTRACT_STATE_VALUES = {"not_frozen", "frozen", "retest_required", "not_applicable"}
CANDIDATE_STATE_VALUES = {"not_fixed", "fixed", "superseded"}
RUNTIME_GATE_VALUES = {"not_assessed", "open", "blocked", "evidence_ready", "passed"}
EVIDENCE_KIND_VALUES = {"document", "handoff", "test_run", "defect"}
EVIDENCE_ITEM_KEYS = frozenset(
    {
        "id",
        "label",
        "kind",
        "status",
        "display_label",
        "source_role",
        "verified_at",
        "checked_at",
        "safe_summary",
        "evidence_level",
        "document_path",
        "reference",
    }
)
SCOPE_ITEM_KEYS = frozenset({"id", "label"})
STATE_SUMMARY_KEYS = frozenset({"status", "safe_summary"})
OPEN_BLOCKER_KEYS = frozenset(
    {"id", "title", "status", "next_action", "updated_at", "evidence_refs"}
)
SAFE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
EVIDENCE_LEVEL_VALUES = {f"D{level}" for level in range(7)}
EVIDENCE_LEVEL_RANK = {f"D{level}": level for level in range(7)}
SOURCE_ROLE_LABELS = {
    "product": "产品负责人",
    "development": "服务端技术负责人",
    "frontend": "前端开发负责人",
    "testing": "测试负责人",
    "project_owner": "项目负责人",
}
WORKSPACE_OWNER_ROLE_LABELS = {
    "project_owner": "项目负责人",
    "development": "服务端技术负责人",
    "frontend": "前端开发负责人",
    "testing": "测试负责人",
}
WORKSPACE_ID_VALUES = {"collaboration", "development", "frontend", "testing"}
WORKSPACE_ITEM_KEYS = frozenset(
    {
        "id",
        "display_label",
        "owner_role",
        "status",
        "current",
        "next",
        "completed_items",
        "updated_at",
        "checked_at",
        "delivery_line_refs",
        "open_blockers",
        "evidence_refs",
    }
)
WORKSPACE_EVIDENCE_REF_KEYS = frozenset({"delivery_line_id", "evidence_id"})
WORKSPACE_COMPLETED_ITEM_KEYS = frozenset(
    {"id", "label", "checked_at", "source_role", "evidence_refs"}
)
WORKSPACE_STATUS_LABELS = {
    "planning": "规划中",
    "contract_freeze": "契约待冻结",
    "implementation": "实施中",
    "integration": "联调中",
    "independent_test": "独立测试中",
    "product_acceptance": "产品验收中",
    "ready_for_trial": "可试用",
}
LOCAL_PATH_MARKER = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|\bfile:|(?:^|\s)/(?:home|users|var|tmp)(?:/|$))",
    re.IGNORECASE,
)


def _require_mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_safe_display_text(value: object, field: str) -> str:
    """Allow a short management summary, never a path or raw diagnostic."""
    text = _require_string(value, field)
    if len(text) > 500 or LOCAL_PATH_MARKER.search(text):
        raise ValueError(f"{field} must be a safe management summary")
    return text


def _reject_undeclared_fields(
    mapping: dict[str, Any], field: str, allowed: frozenset[str]
) -> None:
    """The safe projection is closed: unknown fields must not pass through."""
    extra = set(mapping) - allowed
    if extra:
        raise ValueError(
            f"{field} contains undeclared fields: {', '.join(sorted(extra))}"
        )


def _validate_source_role(value: object, field: str) -> str:
    source_role = _require_string(value, field)
    if source_role not in SOURCE_ROLE_LABELS:
        raise ValueError(f"{field} is not supported")
    return source_role


def _validate_document_path(
    value: object, field: str, *, project_root: Path
) -> str:
    path = _require_string(value, field)
    candidate = Path(path)
    if candidate.is_absolute() or "\\" in path or ".." in candidate.parts:
        raise ValueError(f"{field} must be a safe docs-relative path")
    if not (project_root / "docs" / candidate).is_file():
        raise ValueError(f"{field} must reference an existing document")
    return path


def _test_run_reference_resolves(reference: str, *, project_root: Path) -> bool:
    """A test-run evidence must trace to a real, controlled run on disk."""
    summary_path = project_root / "reports" / "test-runs" / reference / "summary.json"
    if not summary_path.is_file():
        return False
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return _is_valid_test_run(payload)


def _handoff_reference_resolves(reference: str, *, project_root: Path) -> bool:
    """A handoff evidence must trace to a registered formal handoff record."""
    handoffs_dir = project_root / "docs" / "internal" / "handoffs"
    if not handoffs_dir.is_dir():
        return False
    token_pattern = re.compile(rf"(?<![\w-]){re.escape(reference)}(?![\w-])")
    for handoff_path in handoffs_dir.glob("*.md"):
        try:
            source = handoff_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if token_pattern.search(source):
            return True
    return False


def _defect_reference_resolves(reference: str, *, project_root: Path) -> bool:
    try:
        defects = load_defects(project_root=project_root)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return any(item.get("id") == reference for item in defects)


def _validate_evidence_item(item: object, field: str, *, project_root: Path) -> None:
    evidence = _require_mapping(item, field)
    _reject_undeclared_fields(evidence, field, EVIDENCE_ITEM_KEYS)
    _require_string(evidence.get("id"), f"{field}.id")
    _require_string(evidence.get("label"), f"{field}.label")
    kind = _require_string(evidence.get("kind"), f"{field}.kind")
    if kind not in EVIDENCE_KIND_VALUES:
        raise ValueError(f"{field}.kind is not supported")
    _require_string(evidence.get("status"), f"{field}.status")
    _require_string(evidence.get("display_label"), f"{field}.display_label")
    _validate_source_role(evidence.get("source_role"), f"{field}.source_role")
    _require_string(evidence.get("verified_at"), f"{field}.verified_at")
    _require_string(evidence.get("checked_at"), f"{field}.checked_at")
    _require_string(evidence.get("safe_summary"), f"{field}.safe_summary")
    level = evidence.get("evidence_level")
    if level is not None and level not in EVIDENCE_LEVEL_VALUES:
        raise ValueError(f"{field}.evidence_level is not supported")

    if kind == "document":
        _validate_document_path(
            evidence.get("document_path"), f"{field}.document_path", project_root=project_root
        )
        return

    reference = _require_string(evidence.get("reference"), f"{field}.reference")
    if not SAFE_REFERENCE_PATTERN.fullmatch(reference):
        raise ValueError(f"{field}.reference is invalid")
    if kind == "test_run" and not _test_run_reference_resolves(
        reference, project_root=project_root
    ):
        raise ValueError(f"{field}.reference does not trace to a controlled test run")
    if kind == "handoff" and not _handoff_reference_resolves(
        reference, project_root=project_root
    ):
        raise ValueError(f"{field}.reference does not trace to a registered handoff")
    if kind == "defect" and not _defect_reference_resolves(
        reference, project_root=project_root
    ):
        raise ValueError(f"{field}.reference does not trace to a registered defect")


def _validate_delivery_lines(
    project: dict[str, Any], *, project_root: Path = PROJECT_ROOT
) -> None:
    """Validate optional, evidence-only delivery tracking data.

    The management dashboard is deliberately a reader of declared evidence.  It
    does not infer approval from code, test counts, or a candidate commit, and
    every non-document evidence must trace to a real controlled asset.
    """
    delivery_lines = project.get("delivery_lines")
    if delivery_lines is None:
        return
    if not isinstance(delivery_lines, list):
        raise ValueError("delivery_lines must be an array")

    seen_ids: set[str] = set()
    for index, item in enumerate(delivery_lines):
        field = f"delivery_lines[{index}]"
        line = _require_mapping(item, field)
        line_id = _require_string(line.get("id"), f"{field}.id")
        if line_id in seen_ids:
            raise ValueError(f"{field}.id must be unique")
        seen_ids.add(line_id)
        _require_string(line.get("delivery_track"), f"{field}.delivery_track")
        _require_string(line.get("name"), f"{field}.name")
        _require_string(line.get("display_label"), f"{field}.display_label")
        _validate_source_role(line.get("source_role"), f"{field}.source_role")
        _require_string(line.get("verified_at"), f"{field}.verified_at")
        line_level = _require_string(line.get("evidence_level"), f"{field}.evidence_level")
        if line_level not in EVIDENCE_LEVEL_VALUES:
            raise ValueError(f"{field}.evidence_level is not supported")
        status = _require_string(line.get("delivery_status"), f"{field}.delivery_status")
        if status not in DELIVERY_LINE_STATUS_VALUES:
            raise ValueError(f"{field}.delivery_status is not supported")
        _require_string(line.get("summary"), f"{field}.summary")
        _require_string(line.get("updated_at"), f"{field}.updated_at")

        for scope_name in ("scope_in", "scope_out"):
            scope = line.get(scope_name)
            if not isinstance(scope, list):
                raise ValueError(f"{field}.{scope_name} must be an array")
            for scope_index, scope_item in enumerate(scope):
                item_field = f"{field}.{scope_name}[{scope_index}]"
                scope_mapping = _require_mapping(scope_item, item_field)
                _reject_undeclared_fields(scope_mapping, item_field, SCOPE_ITEM_KEYS)
                _require_string(scope_mapping.get("id"), f"{item_field}.id")
                _require_string(scope_mapping.get("label"), f"{item_field}.label")

        contract_state = _require_mapping(line.get("contract_state"), f"{field}.contract_state")
        _reject_undeclared_fields(
            contract_state, f"{field}.contract_state", STATE_SUMMARY_KEYS
        )
        if contract_state.get("status") not in CONTRACT_STATE_VALUES:
            raise ValueError(f"{field}.contract_state.status is not supported")
        _require_string(contract_state.get("safe_summary"), f"{field}.contract_state.safe_summary")

        candidate = _require_mapping(line.get("candidate_version"), f"{field}.candidate_version")
        _reject_undeclared_fields(
            candidate, f"{field}.candidate_version", STATE_SUMMARY_KEYS
        )
        if candidate.get("status") not in CANDIDATE_STATE_VALUES:
            raise ValueError(f"{field}.candidate_version.status is not supported")
        _require_string(candidate.get("safe_summary"), f"{field}.candidate_version.safe_summary")

        runtime_gate = _require_mapping(line.get("runtime_gate"), f"{field}.runtime_gate")
        _reject_undeclared_fields(
            runtime_gate, f"{field}.runtime_gate", STATE_SUMMARY_KEYS
        )
        if runtime_gate.get("status") not in RUNTIME_GATE_VALUES:
            raise ValueError(f"{field}.runtime_gate.status is not supported")
        _require_string(runtime_gate.get("safe_summary"), f"{field}.runtime_gate.safe_summary")

        evidence_links = line.get("evidence_links")
        if not isinstance(evidence_links, list):
            raise ValueError(f"{field}.evidence_links must be an array")
        for evidence_index, evidence in enumerate(evidence_links):
            _validate_evidence_item(
                evidence, f"{field}.evidence_links[{evidence_index}]", project_root=project_root
            )
            if (
                isinstance(evidence, dict)
                and evidence.get("evidence_level") is not None
                and EVIDENCE_LEVEL_RANK[evidence["evidence_level"]]
                > EVIDENCE_LEVEL_RANK[line_level]
            ):
                raise ValueError(
                    f"{field}.evidence_links[{evidence_index}] exceeds line evidence_level"
                )
        evidence_ids = {
            evidence["id"] for evidence in evidence_links if isinstance(evidence, dict)
        }

        open_blockers = line.get("open_blockers")
        if not isinstance(open_blockers, list):
            raise ValueError(f"{field}.open_blockers must be an array")
        for blocker_index, blocker_item in enumerate(open_blockers):
            blocker_field = f"{field}.open_blockers[{blocker_index}]"
            blocker = _require_mapping(blocker_item, blocker_field)
            _reject_undeclared_fields(blocker, blocker_field, OPEN_BLOCKER_KEYS)
            _require_string(blocker.get("id"), f"{blocker_field}.id")
            _require_string(blocker.get("title"), f"{blocker_field}.title")
            _require_string(blocker.get("status"), f"{blocker_field}.status")
            _require_string(blocker.get("next_action"), f"{blocker_field}.next_action")
            _require_string(blocker.get("updated_at"), f"{blocker_field}.updated_at")
            references = blocker.get("evidence_refs", [])
            if not isinstance(references, list) or not set(references) <= evidence_ids:
                raise ValueError(f"{blocker_field}.evidence_refs must reference evidence_links")

        # D5 and D6 are declarations of independently verified readiness, not
        # labels that a browser or a code candidate is allowed to infer.
        if EVIDENCE_LEVEL_RANK[line_level] >= 5:
            has_independent_test = any(
                item.get("kind") == "test_run"
                and item.get("evidence_level") in {"D5", "D6"}
                for item in evidence_links
                if isinstance(item, dict)
            )
            no_open_blockers = not any(
                item.get("status") in {"open", "blocked"}
                for item in open_blockers
                if isinstance(item, dict)
            )
            if (
                candidate.get("status") != "fixed"
                or contract_state.get("status") != "frozen"
                or runtime_gate.get("status") not in {"evidence_ready", "passed"}
                or not has_independent_test
                or not no_open_blockers
            ):
                raise ValueError(f"{field}.evidence_level D5/D6 requires verified gates")
        if EVIDENCE_LEVEL_RANK[line_level] == 6:
            has_product_decision = any(
                item.get("evidence_level") == "D6"
                and item.get("kind") in {"document", "handoff"}
                for item in evidence_links
                if isinstance(item, dict)
            )
            if runtime_gate.get("status") != "passed" or not has_product_decision:
                raise ValueError(f"{field}.evidence_level D6 requires product acceptance evidence")

    known_ids = seen_ids
    for group_name in ("roles", "workspaces"):
        group = project.get(group_name, {})
        if not isinstance(group, dict):
            continue
        for owner, workspace in group.items():
            if not isinstance(workspace, dict) or "delivery_line_refs" not in workspace:
                continue
            references = workspace["delivery_line_refs"]
            if not isinstance(references, list) or not all(
                isinstance(item, str) and item in known_ids for item in references
            ):
                raise ValueError(f"{group_name}.{owner}.delivery_line_refs is invalid")


def _safe_evidence_item(line_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Make a link to a safe evidence projection, never to a raw detail page."""
    return {
        "id": evidence["id"],
        "label": evidence["label"],
        "display_label": evidence["display_label"],
        "source_role": evidence["source_role"],
        "source_role_label": SOURCE_ROLE_LABELS[evidence["source_role"]],
        "kind": evidence["kind"],
        "status": evidence["status"],
        "evidence_level": evidence.get("evidence_level"),
        "verified_at": evidence["verified_at"],
        "checked_at": evidence["checked_at"],
        "safe_summary": evidence["safe_summary"],
        "href": (
            "/api/v1/project-status/dashboard/delivery-lines/"
            f"{line_id}/evidence/{evidence['id']}"
        ),
    }


def _validate_safe_workspaces(project: dict[str, Any], *, project_root: Path) -> None:
    """Validate the optional closed schema used by standalone workspaces.

    The source status document may contain historical role and handoff material,
    but standalone workspace pages never project it.  They accept only the
    purpose-built ``safe_workspaces`` slice below.
    """
    workspaces = project.get("safe_workspaces")
    if workspaces is None:
        return
    if not isinstance(workspaces, list):
        raise ValueError("safe_workspaces must be an array")

    _validate_delivery_lines(project, project_root=project_root)
    lines = {
        line["id"]: line
        for line in project.get("delivery_lines", [])
        if isinstance(line, dict)
    }
    seen_ids: set[str] = set()
    for index, item in enumerate(workspaces):
        field = f"safe_workspaces[{index}]"
        workspace = _require_mapping(item, field)
        _reject_undeclared_fields(workspace, field, WORKSPACE_ITEM_KEYS)
        workspace_id = _require_string(workspace.get("id"), f"{field}.id")
        if workspace_id not in WORKSPACE_ID_VALUES or workspace_id in seen_ids:
            raise ValueError(f"{field}.id is not supported or duplicated")
        seen_ids.add(workspace_id)
        _require_safe_display_text(workspace.get("display_label"), f"{field}.display_label")
        owner_role = _require_string(workspace.get("owner_role"), f"{field}.owner_role")
        if owner_role not in WORKSPACE_OWNER_ROLE_LABELS:
            raise ValueError(f"{field}.owner_role is not supported")
        if workspace.get("status") not in DELIVERY_LINE_STATUS_VALUES:
            raise ValueError(f"{field}.status is not supported")
        for name in ("current", "next", "updated_at", "checked_at"):
            value = workspace.get(name)
            if value is not None:
                _require_safe_display_text(value, f"{field}.{name}")

        line_refs = workspace.get("delivery_line_refs")
        if not isinstance(line_refs, list) or not line_refs:
            raise ValueError(f"{field}.delivery_line_refs must be a non-empty array")
        if not all(isinstance(ref, str) and ref in lines for ref in line_refs):
            raise ValueError(f"{field}.delivery_line_refs must reference delivery_lines")

        evidence_refs = workspace.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            raise ValueError(f"{field}.evidence_refs must be an array")
        available_evidence_ids: set[str] = set()
        for evidence_index, evidence_ref in enumerate(evidence_refs):
            evidence_field = f"{field}.evidence_refs[{evidence_index}]"
            reference = _require_mapping(evidence_ref, evidence_field)
            _reject_undeclared_fields(reference, evidence_field, WORKSPACE_EVIDENCE_REF_KEYS)
            line_id = _require_string(
                reference.get("delivery_line_id"), f"{evidence_field}.delivery_line_id"
            )
            evidence_id = _require_string(
                reference.get("evidence_id"), f"{evidence_field}.evidence_id"
            )
            line = lines.get(line_id)
            if line is None or line_id not in line_refs:
                raise ValueError(f"{evidence_field} must reference a workspace delivery line")
            if evidence_id not in {
                evidence["id"]
                for evidence in line.get("evidence_links", [])
                if isinstance(evidence, dict)
            }:
                raise ValueError(f"{evidence_field} must reference controlled evidence")
            available_evidence_ids.add(evidence_id)

        completed_items = workspace.get("completed_items", [])
        if not isinstance(completed_items, list):
            raise ValueError(f"{field}.completed_items must be an array")
        completed_ids: set[str] = set()
        for completed_index, completed_item in enumerate(completed_items):
            completed_field = f"{field}.completed_items[{completed_index}]"
            completed = _require_mapping(completed_item, completed_field)
            _reject_undeclared_fields(
                completed, completed_field, WORKSPACE_COMPLETED_ITEM_KEYS
            )
            completed_id = _require_string(completed.get("id"), f"{completed_field}.id")
            if (
                not SAFE_REFERENCE_PATTERN.fullmatch(completed_id)
                or completed_id in completed_ids
            ):
                raise ValueError(f"{completed_field}.id is not a safe reference")
            completed_ids.add(completed_id)
            _require_safe_display_text(completed.get("label"), f"{completed_field}.label")
            _require_safe_display_text(
                completed.get("checked_at"), f"{completed_field}.checked_at"
            )
            _validate_source_role(
                completed.get("source_role"), f"{completed_field}.source_role"
            )
            references = completed.get("evidence_refs", [])
            if not isinstance(references, list) or not all(
                isinstance(reference, str) for reference in references
            ):
                raise ValueError(f"{completed_field}.evidence_refs must be an array")
            if not set(references) <= available_evidence_ids:
                raise ValueError(
                    f"{completed_field}.evidence_refs must reference workspace evidence"
                )

        blockers = workspace.get("open_blockers")
        if not isinstance(blockers, list):
            raise ValueError(f"{field}.open_blockers must be an array")
        for blocker_index, blocker_item in enumerate(blockers):
            blocker_field = f"{field}.open_blockers[{blocker_index}]"
            blocker = _require_mapping(blocker_item, blocker_field)
            _reject_undeclared_fields(blocker, blocker_field, OPEN_BLOCKER_KEYS)
            for name in ("id", "title", "status", "next_action", "updated_at"):
                _require_safe_display_text(blocker.get(name), f"{blocker_field}.{name}")
            references = blocker.get("evidence_refs", [])
            if not isinstance(references, list) or not set(references) <= available_evidence_ids:
                raise ValueError(f"{blocker_field}.evidence_refs must reference workspace evidence")


def build_workspace_dashboard_view(
    project: dict[str, Any], *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Return the safe management-only workspace projection.

    Each workspace is declared once in the closed ``safe_workspaces`` schema.
    Evidence is reused from a referenced delivery line so the browser receives
    only the existing controlled evidence endpoint, never a raw URL or path.
    """
    _validate_safe_workspaces(project, project_root=project_root)
    workspaces = project.get("safe_workspaces")
    if not workspaces:
        return {"schema_version": 1, "workspaces": []}

    lines = {
        line["id"]: line
        for line in project.get("delivery_lines", [])
        if isinstance(line, dict)
    }
    safe_workspaces: list[dict[str, Any]] = []
    for workspace in workspaces:
        assert isinstance(workspace, dict)
        safe_evidence = []
        for reference in workspace["evidence_refs"]:
            assert isinstance(reference, dict)
            line = lines[reference["delivery_line_id"]]
            evidence = next(
                item
                for item in line["evidence_links"]
                if isinstance(item, dict) and item["id"] == reference["evidence_id"]
            )
            safe_evidence.append(_safe_evidence_item(line["id"], evidence))
        safe_workspaces.append(
            {
                "id": workspace["id"],
                "display_label": workspace["display_label"],
                "owner_role": workspace["owner_role"],
                "owner_role_label": WORKSPACE_OWNER_ROLE_LABELS[workspace["owner_role"]],
                "status": workspace["status"],
                "status_label": WORKSPACE_STATUS_LABELS[workspace["status"]],
                "current": workspace.get("current"),
                "next": workspace.get("next"),
                "completed_items": [
                    {
                        "id": item["id"],
                        "label": item["label"],
                        "checked_at": item["checked_at"],
                        "source_role": item["source_role"],
                        "source_role_label": SOURCE_ROLE_LABELS[item["source_role"]],
                        "evidence_refs": list(item.get("evidence_refs", [])),
                    }
                    for item in workspace.get("completed_items", [])
                    if isinstance(item, dict)
                ],
                "updated_at": workspace.get("updated_at"),
                "checked_at": workspace.get("checked_at"),
                "delivery_line_refs": list(workspace["delivery_line_refs"]),
                "open_blockers": [
                    _project_open_blocker(blocker)
                    for blocker in workspace["open_blockers"]
                    if isinstance(blocker, dict)
                ],
                "evidence_links": safe_evidence,
            }
        )
    return {"schema_version": 1, "workspaces": safe_workspaces}


def _project_scope_item(item: dict[str, Any]) -> dict[str, Any]:
    return {"id": item["id"], "label": item["label"]}


def _project_state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {key: state[key] for key in STATE_SUMMARY_KEYS}


def _project_open_blocker(blocker: dict[str, Any]) -> dict[str, Any]:
    return {key: blocker[key] for key in OPEN_BLOCKER_KEYS}


def build_delivery_dashboard_view(
    project: dict[str, Any], *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Return a browser-safe, evidence-only delivery tracking projection.

    Every nested structure is rebuilt from an explicit key whitelist so that
    undeclared fields can never pass through, even if validation is bypassed.
    """
    _validate_delivery_lines(project, project_root=project_root)
    if not project.get("delivery_lines"):
        return {"schema_version": 1, "delivery_lines": [], "workspace_refs": {}}

    safe_lines: list[dict[str, Any]] = []
    for line in project["delivery_lines"]:
        safe_evidence = [_safe_evidence_item(line["id"], item) for item in line["evidence_links"]]
        safe_lines.append(
            {
                "id": line["id"],
                "delivery_track": line["delivery_track"],
                "name": line["name"],
                "display_label": line["display_label"],
                "source_role": line["source_role"],
                "source_role_label": SOURCE_ROLE_LABELS[line["source_role"]],
                "evidence_level": line["evidence_level"],
                "verified_at": line["verified_at"],
                "delivery_status": line["delivery_status"],
                "summary": line["summary"],
                "updated_at": line["updated_at"],
                "scope_in": [_project_scope_item(item) for item in line["scope_in"]],
                "scope_out": [_project_scope_item(item) for item in line["scope_out"]],
                "contract_state": _project_state_summary(line["contract_state"]),
                "candidate_version": _project_state_summary(line["candidate_version"]),
                "runtime_gate": _project_state_summary(line["runtime_gate"]),
                "evidence_links": safe_evidence,
                "open_blockers": [
                    _project_open_blocker(blocker) for blocker in line["open_blockers"]
                ],
            }
        )
    workspace_refs = {
        group_name: {
            owner: workspace["delivery_line_refs"]
            for owner, workspace in project.get(group_name, {}).items()
            if isinstance(workspace, dict) and "delivery_line_refs" in workspace
        }
        for group_name in ("roles", "workspaces")
    }
    return {
        "schema_version": 1,
        "delivery_lines": safe_lines,
        "workspace_refs": workspace_refs,
    }


def load_delivery_evidence_view(
    line_id: str, evidence_id: str, *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Load one safe evidence projection without exposing raw source content."""
    project = load_project_status(project_root=project_root)
    for line in project.get("delivery_lines", []):
        if line.get("id") != line_id:
            continue
        for evidence in line.get("evidence_links", []):
            if evidence.get("id") == evidence_id:
                return _safe_evidence_item(line_id, evidence)
    raise KeyError(f"{line_id}/{evidence_id}")


def load_project_status(
    path: Path | None = None, *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Load the owner-facing delivery status from its single source of truth."""
    if path is None:
        path = project_root / "project-status.json"
    with path.open("r", encoding="utf-8") as status_file:
        project = json.load(status_file)
    if not isinstance(project, dict):
        raise ValueError("project-status.json must contain an object")
    _validate_delivery_lines(project, project_root=project_root)
    _validate_safe_workspaces(project, project_root=project_root)
    for stage in project.get("stages", []):
        stage["testing"] = stage_test_summary(stage["code"], project_root=project_root)
    return project


def load_stage(
    stage_code: str, *, project_root: Path = PROJECT_ROOT
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_code = stage_code.upper()
    if not STAGE_CODE_PATTERN.fullmatch(normalized_code):
        raise KeyError(normalized_code)

    project = load_project_status(project_root=project_root)
    stage = next(
        (item for item in project["stages"] if item["code"] == normalized_code),
        None,
    )
    if stage is None:
        raise KeyError(normalized_code)
    return project, stage


def render_stage_requirements(stage_code: str, *, project_root: Path = PROJECT_ROOT) -> str:
    normalized_code = stage_code.upper()
    if not STAGE_CODE_PATTERN.fullmatch(normalized_code):
        raise KeyError(normalized_code)

    # Stage detail pages render the formal PRD from the classified stage directory.
    # Interface contracts are maintained separately under docs/internal.
    stage_requirements_dir = project_root / "docs" / "requirements" / "stages"
    matches = sorted(stage_requirements_dir.glob(f"{normalized_code}-*需求.md"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one requirement document for {normalized_code}")

    source = matches[0].read_text(encoding="utf-8")
    rendered = markdown.markdown(
        source,
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    return sanitize_html(rendered)
