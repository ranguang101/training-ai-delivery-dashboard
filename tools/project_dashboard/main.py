"""Standalone project management dashboard.

This process deliberately does not import ``app.main`` or the business router
registry.  It never initializes a database, runs a migration, mounts business
routes, or loads the business authentication middleware.  It only reuses the
read-only project-status router, templates, and static assets to show local
planning, documents, handoffs, and test evidence.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# This is an explicit operator-selected local tool.  Its availability must not
# be coupled to the business service's production setting for embedded status
# pages.  The override affects this process only.
os.environ["PROJECT_STATUS_ENABLED"] = "true"

from app.routers.project_status import router as project_status_router

DASHBOARD_CODE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DASHBOARD_DATA_ROOT = DASHBOARD_CODE_ROOT / "fixtures" / "demo-project"


def create_dashboard_app(
    project_root: Path | None = None,
    *,
    dashboard_test_fault: str | None = None,
) -> FastAPI:
    """Create the local-only dashboard without business lifecycle hooks."""
    # The dashboard executable owns its templates and static assets.  The
    # optional project root is a read-only data source only, so a dashboard
    # clone never falls back to stale assets from the project being observed.
    root = (project_root or DEFAULT_DASHBOARD_DATA_ROOT).resolve()
    app = FastAPI(
        title="晚托班 AI 教师提效系统｜项目管理面板",
        version="1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.dashboard_project_root = root
    app.state.dashboard_mode = "read_only_local"
    app.state.dashboard_test_fault = dashboard_test_fault
    app.state.project_status_templates = Jinja2Templates(
        directory=str(DASHBOARD_CODE_ROOT / "app" / "templates")
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(DASHBOARD_CODE_ROOT / "app" / "static")),
        name="static",
    )
    app.include_router(project_status_router)
    return app


app = create_dashboard_app()
