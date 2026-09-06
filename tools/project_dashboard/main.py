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
    r3_test_fixture: str | None = None,
    test_fault: str | None = None,
) -> FastAPI:
    """Create the local-only dashboard without business lifecycle hooks."""
    # The dashboard executable owns its templates and static assets.  The
    # optional project root is a read-only data source only, so a dashboard
    # clone never falls back to stale assets from the project being observed.
    root = (project_root or DEFAULT_DASHBOARD_DATA_ROOT).resolve()
    app = FastAPI(
        title="项目交付看板｜本地监控",
        version="1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.dashboard_project_root = root
    app.state.dashboard_mode = "read_only_local"
    app.state.dashboard_r3_test_fixture = r3_test_fixture
    app.state.dashboard_test_fault = test_fault
    app.state.project_status_templates = Jinja2Templates(
        directory=str(DASHBOARD_CODE_ROOT / "app" / "templates")
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(DASHBOARD_CODE_ROOT / "app" / "static")),
        name="static",
    )
    app.include_router(project_status_router)

    @app.get("/", include_in_schema=False)
    def root_redirect():
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/project-status/v2")

    return app


app = create_dashboard_app()
