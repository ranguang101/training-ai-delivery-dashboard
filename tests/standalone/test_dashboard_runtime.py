"""Standalone R3 startup and loopback boundary checks."""

import pytest
from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app
from tools.project_dashboard.run import resolve_loopback_host


def test_default_demo_starts_with_r3_safe_projection_only() -> None:
    with TestClient(create_dashboard_app()) as client:
        workspace = client.get("/api/v1/project-status/dashboard/r3/workspaces/collaboration")
        assert workspace.status_code == 200
        data = workspace.json()["data"]
        assert len(data["line_options"]) == 3
        assert set(data["cards"]) == {
            "conclusion",
            "progress",
            "gates_and_blockers",
            "checked_evidence",
        }

        sync = client.get("/api/v1/project-status")
        assert sync.status_code == 200
        assert set(sync.json()["data"]) == {"project_name", "last_updated"}

        # R2 raw-data and auxiliary-operation surfaces are not part of R3.
        assert client.get("/api/v1/project-status/dashboard").status_code == 404
        assert client.get("/project-status/tests/automation").status_code == 404


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_loopback_hosts_are_allowed(host: str) -> None:
    assert resolve_loopback_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com"])
def test_non_loopback_hosts_are_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="DASHBOARD_LOOPBACK_ONLY"):
        resolve_loopback_host(host)
