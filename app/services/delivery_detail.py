"""Generic delivery-line detail and controlled evidence projections.

This service is deliberately additive to the R3/R4 projections.  The R3
delivery line remains the source of the L1 summary and the R4 service remains
the source of quality lifecycle data.  This module only validates explicit
cross-object relationships and rebuilds a small, safe L2/L4 projection.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.services.delivery_monitor import (
    EVIDENCE_TYPE_VALUES,
    build_r3_workspace_view,
)
from app.services.project_status_cache import load_project_status
from app.services.quality_lifecycle import (
    QualityLifecycleNotFound,
    build_quality_requirement_overview,
)

DETAIL_SECTION_KEY = "delivery_detail"
DETAIL_SECTION_KEYS = frozenset(
    {
        "schema_version",
        "delivery_line_relations",
        "requirement_revisions",
        "technical_solutions",
        "candidate_handoffs",
        "quality_links",
        "evidence_projections",
    }
)
REVISION_STATUS_VALUES = frozenset({"proposed", "confirmed", "superseded", "withdrawn"})
SOLUTION_STATUS_VALUES = frozenset(
    {"planned", "in_review", "approved", "implementation", "verified", "superseded", "blocked"}
)
CANDIDATE_STATUS_VALUES = frozenset({"pending", "fixed", "inconsistent"})
EVIDENCE_VALIDITY_VALUES = frozenset({"valid", "stale", "missing", "unavailable", "conflict"})
HANDOFF_ITEM_STATUS_VALUES = frozenset({"provided", "missing", "conflict", "pending"})
REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
STALE_AFTER = timedelta(hours=72)


class DeliveryDetailNotFound(KeyError):
    """The requested delivery line or controlled evidence is not registered."""


def _warning(code: str, safe_message: str) -> dict[str, str]:
    return {"code": code, "safe_message": safe_message}


def _dedupe_warnings(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        key = (item["code"], item["safe_message"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _reference(value: Any) -> str:
    if not isinstance(value, str) or not REFERENCE_PATTERN.fullmatch(value):
        raise ValueError("invalid stable reference")
    return value


def _text(value: Any, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid safe text")
    value = value.strip()
    if len(value) > maximum or "file:" in value.lower() or "http://" in value.lower():
        raise ValueError("unsafe safe text")
    if "https://" in value.lower() or "\\" in value or "\r" in value or "\n" in value:
        raise ValueError("unsafe safe text")
    return value


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed > datetime.now(UTC):
        return None
    return value


def _verification_state(value: str | None) -> str:
    if value is None:
        return "missing"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return "stale" if parsed <= datetime.now(UTC) - STALE_AFTER else "verified"


def _refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("invalid reference list")
    return [_reference(item) for item in value]


def _text_list(value: Any, *, maximum: int) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("invalid safe text list")
    return [_text(item, maximum=maximum) for item in value]


def _evidence_refs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("invalid evidence reference list")
    result = []
    for item in value:
        item = _closed(item, frozenset({"evidence_type", "evidence_id"}))
        evidence_type = _text(item.get("evidence_type"), maximum=32)
        if evidence_type not in EVIDENCE_TYPE_VALUES:
            raise ValueError("invalid evidence type")
        result.append(
            {
                "evidence_type": evidence_type,
                "evidence_id": _reference(item.get("evidence_id")),
            }
        )
    return result


def _closed(item: Any, allowed: frozenset[str]) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) - allowed:
        raise ValueError("unexpected object fields")
    return item


def _parse_line_relation(item: Any) -> dict[str, Any]:
    raw = _closed(
        item,
        frozenset(
            {
                "delivery_line_id",
                "requirement_revision_refs",
                "technical_solution_refs",
                "candidate_handoff_refs",
                "quality_requirement_refs",
                "evidence_refs",
            }
        ),
    )
    return {
        "delivery_line_id": _reference(raw.get("delivery_line_id")),
        "requirement_revision_refs": _refs(raw.get("requirement_revision_refs", [])),
        "technical_solution_refs": _refs(raw.get("technical_solution_refs", [])),
        "candidate_handoff_refs": _refs(raw.get("candidate_handoff_refs", [])),
        "quality_requirement_refs": _refs(raw.get("quality_requirement_refs", [])),
        "evidence_refs": _evidence_refs(raw.get("evidence_refs", [])),
    }


def _parse_revision(item: Any) -> dict[str, Any]:
    raw = _closed(
        item,
        frozenset(
            {
                "revision_id",
                "delivery_line_id",
                "revision_label",
                "revision_status",
                "effective_at",
                "change_refs",
                "change_summary",
                "scope_delta",
                "owner_role",
                "verified_at",
                "evidence_refs",
            }
        ),
    )
    status = _text(raw.get("revision_status"), maximum=32)
    if status not in REVISION_STATUS_VALUES:
        raise ValueError("invalid revision status")
    effective_at = _timestamp(raw.get("effective_at"))
    verified_at = _timestamp(raw.get("verified_at"))
    return {
        "revision_id": _reference(raw.get("revision_id")),
        "delivery_line_id": _reference(raw.get("delivery_line_id")),
        "revision_label": _text(raw.get("revision_label"), maximum=160),
        "revision_status": status,
        "effective_at": effective_at,
        "change_refs": _refs(raw.get("change_refs", [])),
        "change_summary": _text(raw.get("change_summary", "变更摘要待关联")),
        "scope_delta": _text(raw.get("scope_delta", "范围变化摘要待关联")),
        "owner_role": _text(raw.get("owner_role", "责任角色待关联"), maximum=64),
        "verified_at": verified_at,
        "verification_state": _verification_state(verified_at),
        "evidence_refs": _evidence_refs(raw.get("evidence_refs", [])),
    }


def _parse_solution(item: Any) -> dict[str, Any]:
    raw = _closed(
        item,
        frozenset(
            {
                "technical_solution_id",
                "delivery_line_id",
                "revision_id",
                "solution_type",
                "solution_status",
                "title",
                "controlled_summary",
                "owner_role",
                "verified_at",
                "candidate_refs",
                "evidence_refs",
            }
        ),
    )
    status = _text(raw.get("solution_status"), maximum=32)
    if status not in SOLUTION_STATUS_VALUES:
        raise ValueError("invalid solution status")
    verified_at = _timestamp(raw.get("verified_at"))
    return {
        "technical_solution_id": _reference(raw.get("technical_solution_id")),
        "delivery_line_id": _reference(raw.get("delivery_line_id")),
        "revision_id": _reference(raw.get("revision_id")) if raw.get("revision_id") else None,
        "solution_type": _text(raw.get("solution_type"), maximum=64),
        "solution_status": status,
        "title": _text(raw.get("title"), maximum=200),
        "controlled_summary": _text(raw.get("controlled_summary")),
        "owner_role": _text(raw.get("owner_role", "责任角色待关联"), maximum=64),
        "verified_at": verified_at,
        "verification_state": _verification_state(verified_at),
        "candidate_refs": _refs(raw.get("candidate_refs", [])),
        "evidence_refs": _evidence_refs(raw.get("evidence_refs", [])),
    }


def _parse_candidate(item: Any) -> dict[str, Any]:
    raw = _closed(
        item,
        frozenset(
            {
                "candidate_handoff_id",
                "delivery_line_id",
                "technical_solution_refs",
                "candidate_type",
                "handoff_items",
                "candidate_status",
                "missing_items",
                "conflict_items",
                "verified_at",
                "quality_requirement_refs",
                "evidence_refs",
            }
        ),
    )
    status = _text(raw.get("candidate_status"), maximum=32)
    if status not in CANDIDATE_STATUS_VALUES:
        raise ValueError("invalid candidate status")
    items = raw.get("handoff_items", [])
    if not isinstance(items, list):
        raise ValueError("invalid handoff items")
    safe_items = []
    for item_data in items:
        item_data = _closed(item_data, frozenset({"item_type", "safe_summary", "status"}))
        item_status = _text(item_data.get("status"), maximum=32)
        if item_status not in HANDOFF_ITEM_STATUS_VALUES:
            raise ValueError("invalid handoff item status")
        safe_items.append(
            {
                "item_type": _text(item_data.get("item_type"), maximum=64),
                "safe_summary": _text(item_data.get("safe_summary")),
                "status": item_status,
            }
        )
    verified_at = _timestamp(raw.get("verified_at"))
    missing_items = _text_list(raw.get("missing_items", []), maximum=160)
    conflict_items = _text_list(raw.get("conflict_items", []), maximum=160)
    if status == "fixed" and (missing_items or conflict_items):
        status = "inconsistent"
    return {
        "candidate_handoff_id": _reference(raw.get("candidate_handoff_id")),
        "delivery_line_id": _reference(raw.get("delivery_line_id")),
        "technical_solution_refs": _refs(raw.get("technical_solution_refs", [])),
        "candidate_type": _text(raw.get("candidate_type"), maximum=64),
        "handoff_items": safe_items,
        "candidate_status": status,
        "missing_items": missing_items,
        "conflict_items": conflict_items,
        "verified_at": verified_at,
        "verification_state": _verification_state(verified_at),
        "quality_requirement_refs": _refs(raw.get("quality_requirement_refs", [])),
        "evidence_refs": _evidence_refs(raw.get("evidence_refs", [])),
    }


def _parse_quality_link(item: Any) -> dict[str, Any]:
    raw = _closed(
        item,
        frozenset(
            {
                "delivery_line_id",
                "quality_requirement_id",
                "requirement_revision_id",
                "candidate_handoff_id",
            }
        ),
    )
    return {
        "delivery_line_id": _reference(raw.get("delivery_line_id")),
        "quality_requirement_id": _reference(raw.get("quality_requirement_id")),
        "requirement_revision_id": (
            _reference(raw["requirement_revision_id"])
            if raw.get("requirement_revision_id")
            else None
        ),
        "candidate_handoff_id": (
            _reference(raw["candidate_handoff_id"])
            if raw.get("candidate_handoff_id")
            else None
        ),
    }


def _parse_evidence(item: Any) -> dict[str, Any]:
    raw = _closed(
        item,
        frozenset(
            {
                "evidence_id",
                "evidence_type",
                "delivery_line_id",
                "safe_title",
                "safe_summary",
                "source_role",
                "verified_at",
                "validity_state",
                "related_object_refs",
            }
        ),
    )
    evidence_type = _text(raw.get("evidence_type"), maximum=32)
    if evidence_type not in EVIDENCE_TYPE_VALUES:
        raise ValueError("invalid evidence type")
    validity_state = _text(raw.get("validity_state"), maximum=32)
    if validity_state not in EVIDENCE_VALIDITY_VALUES:
        raise ValueError("invalid evidence state")
    related = raw.get("related_object_refs", [])
    if not isinstance(related, list):
        raise ValueError("invalid related object refs")
    related_refs = []
    for item_ref in related:
        item_ref = _closed(item_ref, frozenset({"object_type", "object_id"}))
        related_refs.append(
            {
                "object_type": _text(item_ref.get("object_type"), maximum=64),
                "object_id": _reference(item_ref.get("object_id")),
            }
        )
    verified_at = _timestamp(raw.get("verified_at"))
    effective_state = validity_state
    if effective_state == "valid" and _verification_state(verified_at) == "stale":
        effective_state = "stale"
    return {
        "evidence_id": _reference(raw.get("evidence_id")),
        "evidence_type": evidence_type,
        "delivery_line_id": _reference(raw.get("delivery_line_id")),
        "safe_title": _text(raw.get("safe_title"), maximum=200),
        "safe_summary": _text(raw.get("safe_summary")),
        "source_role": _text(raw.get("source_role"), maximum=64),
        "verified_at": verified_at,
        "validity_state": effective_state,
        "related_object_refs": related_refs,
    }


def _list_items(section: dict[str, Any], key: str) -> tuple[list[Any], list[dict[str, str]]]:
    value = section.get(key, [])
    if not isinstance(value, list):
        return [], [_warning("DD_INVALID_DATA", "部分详情数据格式无效，已安全忽略")]
    return value, []


def _parse_records(section: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    if set(section) - DETAIL_SECTION_KEYS:
        warnings.append(_warning("DD_INVALID_DATA", "详情数据包含未登记字段，已安全降级"))
    parsers = {
        "delivery_line_relations": _parse_line_relation,
        "requirement_revisions": _parse_revision,
        "technical_solutions": _parse_solution,
        "candidate_handoffs": _parse_candidate,
        "quality_links": _parse_quality_link,
        "evidence_projections": _parse_evidence,
    }
    records: dict[str, Any] = {}
    for key, parser in parsers.items():
        values, item_warnings = _list_items(section, key)
        warnings.extend(item_warnings)
        parsed: dict[str, Any] = {}
        for item in values:
            try:
                safe = parser(item)
                if key == "quality_links":
                    stable_key = f"{safe['delivery_line_id']}::{safe['quality_requirement_id']}"
                else:
                    stable_key = safe[
                        {
                            "delivery_line_relations": "delivery_line_id",
                            "requirement_revisions": "revision_id",
                            "technical_solutions": "technical_solution_id",
                            "candidate_handoffs": "candidate_handoff_id",
                            "evidence_projections": "evidence_id",
                        }[key]
                    ]
                if stable_key in parsed:
                    raise ValueError("duplicate stable reference")
                parsed[stable_key] = safe
            except (TypeError, ValueError, KeyError):
                warnings.append(
                    _warning("DD_INVALID_DATA", "部分详情对象未通过完整性校验，已安全忽略")
                )
        records[key] = parsed
    return records, warnings


def _safe_line(project_root: Path, delivery_line_id: str) -> dict[str, Any]:
    try:
        view = build_r3_workspace_view(
            "collaboration", line_id=delivery_line_id, project_root=project_root
        )
    except KeyError as exc:
        raise DeliveryDetailNotFound(delivery_line_id) from exc
    items = view.get("cards", {}).get("conclusion", {}).get("items", [])
    line = next(
        (
            item
            for item in items
            if isinstance(item, dict) and item.get("delivery_line_id") == delivery_line_id
        ),
        None,
    )
    if not isinstance(line, dict):
        try:
            payload = load_project_status(project_root).payload
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise DeliveryDetailNotFound(delivery_line_id) from exc
        raw_lines = payload.get("delivery_lines") if isinstance(payload, dict) else None
        raw_line = next(
            (
                item
                for item in raw_lines
                if isinstance(item, dict)
                and (item.get("delivery_line_id") or item.get("id")) == delivery_line_id
            ),
            None,
        ) if isinstance(raw_lines, list) else None
        if not isinstance(raw_line, dict):
            raise DeliveryDetailNotFound(delivery_line_id)
        return {
            "delivery_line_id": delivery_line_id,
            "name": raw_line.get("name") or raw_line.get("display_label"),
            "scope_summary": raw_line.get("scope_summary") or raw_line.get("summary"),
            "delivery_status": raw_line.get("delivery_status") or raw_line.get("status"),
            "delivery_status_label": raw_line.get("display_label"),
            "current_conclusion": raw_line.get("summary"),
            "current_candidate_summary": "当前候选摘要待关联",
            "next_gate_summary": (
                raw_line.get("open_blockers", [{}])[0].get("next_action")
                if isinstance(raw_line.get("open_blockers"), list)
                and raw_line.get("open_blockers")
                and isinstance(raw_line.get("open_blockers")[0], dict)
                else "下一道门待关联"
            ),
            "can_enter_product_acceptance": None,
            "can_enter_controlled_trial": None,
            "verified_at": raw_line.get("verified_at"),
        }
    allowed = (
        "delivery_line_id",
        "name",
        "scope_summary",
        "delivery_status",
        "delivery_status_label",
        "current_conclusion",
        "current_candidate_summary",
        "next_gate_summary",
        "can_enter_product_acceptance",
        "can_enter_controlled_trial",
        "verified_at",
    )
    return {key: line.get(key) for key in allowed}


def _empty_projection(line: dict[str, Any], warning: dict[str, str]) -> dict[str, Any]:
    return {
        "state": "unlinked",
        "delivery_line": line,
        "summary": {
            "current_revision_id": None,
            "technical_solution_count": 0,
            "candidate_handoff_count": 0,
            "quality_requirement_count": 0,
            "evidence_count": 0,
            "safe_summary": "详情资料待关联",
        },
        "sections": {
            "requirement_revisions": [],
            "technical_solutions": [],
            "candidate_handoffs": [],
            "quality_trace": [],
            "evidence": [],
        },
        "warnings": [warning],
    }


def _section_for(project_root: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        payload = load_project_status(project_root).payload
    except (OSError, UnicodeDecodeError, ValueError):
        return None, [_warning("DD_DATA_UNAVAILABLE", "详情资料暂时无法加载，请稍后重试")]
    if not isinstance(payload, dict):
        return None, [_warning("DD_DATA_UNAVAILABLE", "详情资料暂时无法加载，请稍后重试")]
    section = payload.get(DETAIL_SECTION_KEY)
    if section is None:
        return None, [_warning("DD_DETAIL_NOT_LINKED", "详情资料待关联")]
    if not isinstance(section, dict):
        return None, [_warning("DD_DATA_UNAVAILABLE", "详情资料格式无效，已安全降级")]
    return section, []


def _valid_refs(
    records: dict[str, Any], refs: list[str], *, line_id: str, warning_code: str
) -> tuple[list[str], list[dict[str, str]]]:
    valid: list[str] = []
    warnings: list[dict[str, str]] = []
    for ref in refs:
        item = records.get(ref)
        if not isinstance(item, dict) or item.get("delivery_line_id") != line_id:
            warnings.append(_warning(warning_code, "详情关系缺失或交付线不一致，当前待核对"))
        else:
            valid.append(ref)
    return valid, warnings


def _quality_trace(
    quality_links: dict[str, dict[str, Any]],
    *,
    line_id: str,
    project_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    result: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for link in quality_links.values():
        if link["delivery_line_id"] != line_id:
            continue
        try:
            overview = build_quality_requirement_overview(
                project_root=project_root,
                requirement_id=link["quality_requirement_id"],
                line_id=line_id,
            )
        except QualityLifecycleNotFound:
            warnings.append(_warning("DD_QUALITY_NOT_LINKED", "质量对象待关联，当前不展示质量结论"))
            continue
        selected = overview.get("selected_requirement")
        if not isinstance(selected, dict):
            warnings.append(_warning("DD_QUALITY_NOT_LINKED", "质量对象待关联，当前不展示质量结论"))
            continue
        result.append(
            {
                "quality_requirement_id": selected["quality_requirement_id"],
                "delivery_line_id": selected["delivery_line_id"],
                "name": selected["name"],
                "status": selected["status"],
                "status_label": selected["status_label"],
                "readiness_summary": selected["readiness_summary"],
                "can_enter_product_acceptance": selected["can_enter_product_acceptance"],
                "requirement_revision_id": link["requirement_revision_id"],
                "candidate_handoff_id": link["candidate_handoff_id"],
            }
        )
    return result, warnings


def build_delivery_line_detail(
    delivery_line_id: str, *, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Build the generic L2 projection for one R3 delivery line."""
    delivery_line_id = _reference(delivery_line_id)
    line = _safe_line(project_root, delivery_line_id)
    section, warnings = _section_for(project_root)
    if section is None:
        return _empty_projection(line, warnings[0])
    records, parse_warnings = _parse_records(section)
    warnings.extend(parse_warnings)
    relations = records["delivery_line_relations"].get(delivery_line_id)
    if relations is None:
        return _empty_projection(line, _warning("DD_DETAIL_NOT_LINKED", "详情资料待关联"))
    if relations["delivery_line_id"] != delivery_line_id:
        return _empty_projection(
            line, _warning("DD_LINE_MISMATCH", "详情关系与交付线不匹配，请重新选择")
        )

    revision_refs, relation_warnings = _valid_refs(
        records["requirement_revisions"],
        relations["requirement_revision_refs"],
        line_id=delivery_line_id,
        warning_code="DD_RELATION_MISSING",
    )
    solution_refs, more_warnings = _valid_refs(
        records["technical_solutions"],
        relations["technical_solution_refs"],
        line_id=delivery_line_id,
        warning_code="DD_RELATION_MISSING",
    )
    candidate_refs, more_candidate_warnings = _valid_refs(
        records["candidate_handoffs"],
        relations["candidate_handoff_refs"],
        line_id=delivery_line_id,
        warning_code="DD_RELATION_MISSING",
    )
    warnings.extend(relation_warnings + more_warnings + more_candidate_warnings)
    revisions = [records["requirement_revisions"][ref] for ref in revision_refs]
    current = [item for item in revisions if item["revision_status"] == "confirmed"]
    current_revision_id = current[0]["revision_id"] if len(current) == 1 else None
    if len(current) != 1 and revisions:
        warnings.append(_warning("DD_REVISION_CONFLICT", "当前需求版本状态待核对"))
    for item in revisions:
        item["is_current"] = item["revision_id"] == current_revision_id
    solutions = [records["technical_solutions"][ref] for ref in solution_refs]
    candidates = [records["candidate_handoffs"][ref] for ref in candidate_refs]
    quality_trace, quality_warnings = _quality_trace(
        records["quality_links"], line_id=delivery_line_id, project_root=project_root
    )
    warnings.extend(quality_warnings)
    evidence = []
    evidence_map = records["evidence_projections"]
    for ref in relations["evidence_refs"]:
        if not isinstance(ref, dict):
            warnings.append(_warning("DD_EVIDENCE_UNAVAILABLE", "证据暂不可查看"))
            continue
        try:
            evidence_type = _text(ref.get("evidence_type"), maximum=32)
            evidence_id = _reference(ref.get("evidence_id"))
        except ValueError:
            warnings.append(_warning("DD_EVIDENCE_UNAVAILABLE", "证据暂不可查看"))
            continue
        item = evidence_map.get(evidence_id)
        if (
            isinstance(item, dict)
            and item["delivery_line_id"] == delivery_line_id
            and item["evidence_type"] == evidence_type
        ):
            evidence.append(item)
        else:
            warnings.append(_warning("DD_EVIDENCE_UNAVAILABLE", "证据暂不可查看"))
    if any(item["verification_state"] == "stale" for item in revisions + solutions + candidates):
        warnings.append(_warning("DD_STALE_DATA", "部分详情核对已过期，当前待复核"))
    if any(item["verification_state"] == "missing" for item in revisions + solutions + candidates):
        warnings.append(_warning("DD_MISSING_DATA", "部分详情核对时间缺失，当前待关联"))
    if any(item["candidate_status"] == "inconsistent" for item in candidates):
        warnings.append(_warning("DD_CONFLICT", "候选交接存在冲突，当前待核对"))
    if any(item["validity_state"] in {"stale", "conflict"} for item in evidence):
        warnings.append(_warning("DD_STALE_DATA", "部分证据核对已过期或冲突，当前待复核"))
    if any(item["validity_state"] in {"missing", "unavailable"} for item in evidence):
        warnings.append(_warning("DD_EVIDENCE_UNAVAILABLE", "部分证据暂不可查看"))
    warnings = _dedupe_warnings(warnings)
    state = "ready" if not warnings else "incomplete"
    if not revisions and not solutions and not candidates and not quality_trace and not evidence:
        state = "empty"
    return {
        "state": state,
        "delivery_line": line,
        "summary": {
            "current_revision_id": current_revision_id,
            "technical_solution_count": len(solutions),
            "candidate_handoff_count": len(candidates),
            "quality_requirement_count": len(quality_trace),
            "evidence_count": len(evidence),
            "safe_summary": "详情关系已建立" if state == "ready" else "部分详情关系待核对",
        },
        "sections": {
            "requirement_revisions": revisions,
            "technical_solutions": solutions,
            "candidate_handoffs": candidates,
            "quality_trace": quality_trace,
            "evidence": evidence,
        },
        "warnings": warnings,
    }


def build_delivery_line_evidence_detail(
    delivery_line_id: str,
    evidence_type: str,
    evidence_id: str,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Return one evidence projection only if explicitly linked to the line."""
    detail = build_delivery_line_detail(delivery_line_id, project_root=project_root)
    for item in detail["sections"]["evidence"]:
        if item["evidence_type"] == evidence_type and item["evidence_id"] == evidence_id:
            return {
                **item,
                "return_context": {"delivery_line_id": delivery_line_id},
            }
    raise DeliveryDetailNotFound((delivery_line_id, evidence_type, evidence_id))
