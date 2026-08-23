import hashlib
import json
import re
from pathlib import Path
from typing import Any

import markdown

from app.core.config import PROJECT_ROOT
from app.services.markdown_safety import sanitize_html

DOCUMENTS_DIR = PROJECT_ROOT / "docs"
DOCUMENT_STATUS_PATH = DOCUMENTS_DIR / "document-status.json"

CATEGORY_LABELS = {
    "root": "总览与索引",
    "owner": "负责人文档",
    "requirements": "需求规格",
    "internal": "开发内部资料",
    "testing": "测试资料",
    "references": "参考资料",
    "archive": "历史归档",
}

STATUS_LABELS = {
    "current": "当前有效",
    "superseded": "已被替代",
    "historical": "历史归档",
    "unclassified": "待整理",
}

STATUS_ORDER = {"current": 0, "unclassified": 1, "superseded": 2, "historical": 3}
CATEGORY_ORDER = {name: index for index, name in enumerate(CATEGORY_LABELS)}
STAGE_PATTERN = re.compile(r"(?:^|[^A-Z0-9])(P[0-8])(?:[^A-Z0-9]|$)", re.IGNORECASE)


def _documents_dir(project_root: Path | None) -> Path:
    if project_root is None:
        return DOCUMENTS_DIR
    return project_root / DOCUMENTS_DIR.relative_to(PROJECT_ROOT)


def _load_metadata(
    project_root: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """A corrupt status list must degrade to unclassified, never raise."""
    status_path = _documents_dir(project_root) / "document-status.json"
    if not status_path.exists():
        return {}, None
    try:
        with status_path.open("r", encoding="utf-8") as metadata_file:
            payload = json.load(metadata_file)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}, "文档状态清单无法读取，已安全降级显示。"
    if not isinstance(payload, dict):
        return {}, "文档状态清单格式无效，已安全降级显示。"
    documents = payload.get("documents", {})
    if not isinstance(documents, dict):
        return {}, "文档状态清单格式无效，已安全降级显示。"
    return documents, None


def _read_title(source: str, fallback: str) -> str:
    for line in source.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _read_summary(source: str) -> str:
    for line in source.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith(("#", ">", "-", "|", "`")):
            continue
        return candidate[:120]
    return "尚未填写摘要，可打开文档查看完整内容。"


def _document_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:12]


def build_document_catalog(project_root: Path | None = None) -> dict[str, Any]:
    """A single unreadable document must degrade, never make the page 500."""
    documents_dir = _documents_dir(project_root)
    metadata, metadata_warning = _load_metadata(project_root)
    documents: list[dict[str, Any]] = []
    warnings: list[str] = []
    if metadata_warning:
        warnings.append(metadata_warning)

    if not documents_dir.is_dir():
        warnings.append("项目文档目录不可用，当前不显示任何文档。")
        return {
            "documents": documents,
            "groups": [],
            "total": 0,
            "current": 0,
            "archived": 0,
            "warnings": warnings,
        }

    for path in documents_dir.rglob("*.md"):
        relative_path = path.relative_to(documents_dir).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            warnings.append("存在无法读取的项目文档，已从列表中安全降级。")
            continue
        parts = Path(relative_path).parts
        category = parts[0] if len(parts) > 1 else "root"
        category = category if category in CATEGORY_LABELS else "root"
        configured = metadata.get(relative_path)
        if not isinstance(configured, dict):
            configured = {}
        default_status = "historical" if category == "archive" else "current"
        stage_match = STAGE_PATTERN.search(path.stem)

        documents.append(
            {
                "id": _document_id(relative_path),
                "title": _read_title(source, path.stem),
                "summary": configured.get("summary") or _read_summary(source),
                "relative_path": relative_path,
                "category": category,
                "category_label": CATEGORY_LABELS[category],
                "status": configured.get("status", default_status),
                "replacement": configured.get("replacement"),
                "stage": stage_match.group(1).upper() if stage_match else None,
            }
        )

    documents.sort(
        key=lambda item: (
            STATUS_ORDER.get(item["status"], 99),
            CATEGORY_ORDER.get(item["category"], 99),
            item["relative_path"],
        )
    )

    groups = []
    for category, label in CATEGORY_LABELS.items():
        category_documents = [item for item in documents if item["category"] == category]
        if category_documents:
            groups.append({"key": category, "label": label, "documents": category_documents})

    return {
        "documents": documents,
        "groups": groups,
        "total": len(documents),
        "current": sum(item["status"] == "current" for item in documents),
        "archived": sum(item["status"] in {"superseded", "historical"} for item in documents),
        "warnings": warnings,
    }


def load_document(document_id: str, *, project_root: Path | None = None) -> dict[str, Any]:
    catalog = build_document_catalog(project_root)
    document = next((item for item in catalog["documents"] if item["id"] == document_id), None)
    if document is None:
        raise KeyError(document_id)

    documents_dir = _documents_dir(project_root)
    path = documents_dir / document["relative_path"]
    resolved = path.resolve()
    if documents_dir.resolve() not in resolved.parents or not resolved.is_file():
        raise KeyError(document_id)

    try:
        document["source"] = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise KeyError(document_id) from exc
    return document


def render_document(document: dict[str, Any]) -> str:
    rendered = markdown.markdown(
        document["source"],
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )
    return sanitize_html(rendered)
