"""The dashboard service must remain independent from business startup."""

from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app


def test_dashboard_runs_without_business_lifespan_or_database_state() -> None:
    dashboard = create_dashboard_app()
    assert dashboard.state.dashboard_mode == "read_only_local"
    assert not any(
        getattr(route, "path", None) == "/api/v1/auth/login"
        for route in dashboard.routes
    )

    with TestClient(dashboard) as client:
        response = client.get("/project-status")

    assert response.status_code == 200
    assert "项目交付看板" in response.text


def test_standalone_dashboard_does_not_serve_raw_workspace_pages() -> None:
    """Raw collaboration/development/frontend pages are not panel data entries."""
    with TestClient(create_dashboard_app()) as client:
        for path in (
            "/project-status/collaboration",
            "/project-status/development",
            "/project-status/frontend",
        ):
            response = client.get(path)
            assert response.status_code == 404
            assert response.json()["detail"] == "PROJECT_STATUS_ROUTE_CLOSED_IN_PANEL"
