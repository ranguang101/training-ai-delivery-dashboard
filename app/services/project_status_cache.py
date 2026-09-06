"""Process-local cache for the controlled project-status source."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class ProjectStatusSnapshot:
    """A parsed source payload and the opaque revision used for refresh checks."""

    payload: Any
    revision: str | None


_CACHE_PATH: str | None = None
_CACHE_SNAPSHOT: ProjectStatusSnapshot | None = None
_CACHE_LOCK = RLock()


def project_status_revision(project_root: Path) -> str | None:
    """Return a non-path source fingerprint without reading the payload."""
    try:
        stat = (project_root / "project-status.json").stat()
    except OSError:
        return None
    source = f"{stat.st_mtime_ns}:{stat.st_size}".encode("ascii")
    return hashlib.sha256(source).hexdigest()[:16]


def load_project_status(project_root: Path) -> ProjectStatusSnapshot:
    """Read and cache the parsed status source until its file revision changes.

    The cache is only an in-process acceleration layer. The file remains the
    source of truth, and every lookup checks its metadata before using a
    cached parse. Callers still own validation and safe projection.
    """
    global _CACHE_PATH, _CACHE_SNAPSHOT

    status_path = (project_root / "project-status.json").resolve()
    key = str(status_path)
    revision = project_status_revision(project_root)
    with _CACHE_LOCK:
        if (
            key == _CACHE_PATH
            and _CACHE_SNAPSHOT is not None
            and _CACHE_SNAPSHOT.revision == revision
        ):
            return ProjectStatusSnapshot(copy.deepcopy(_CACHE_SNAPSHOT.payload), revision)

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    snapshot = ProjectStatusSnapshot(payload, revision)
    with _CACHE_LOCK:
        _CACHE_PATH = key
        _CACHE_SNAPSHOT = snapshot
    return ProjectStatusSnapshot(copy.deepcopy(payload), revision)
