import json

import pytest
from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app
from tools.project_dashboard.run import resolve_loopback_host


def test_default_demo_starts_with_only_safe_projections() -> None:
    with TestClient(create_dashboard_app()) as client:
        dashboard = client.get("/api/v1/project-status/dashboard")
        assert dashboard.status_code == 200
        lines = dashboard.json()["data"]["delivery_lines"]
        assert [line["id"] for line in lines] == [
            "mvp-a-management-foundation",
            "mvp-b-manual-daily-record",
            "mvp-b-text-ai-enhancement",
        ]
        assert "D:" not in json.dumps(dashboard.json(), ensure_ascii=False)

        sync = client.get("/api/v1/project-status")
        assert sync.status_code == 200
        assert set(sync.json()["data"]) == {"project_name", "last_updated"}

        automation = client.get("/api/v1/project-status/test-automation")
        assert automation.status_code == 200
        assert automation.json()["data"]["summary"] == {
            "listed_runs": 1,
            "formal_case_statistics_changed": False,
            "release_decision_changed": False,
        }
        assert client.get("/project-status").status_code == 200
        assert client.get("/project-status/tests").status_code == 200
        assert client.get("/project-status/documents").status_code == 404


def test_invalid_external_status_root_degrades_without_a_server_error(tmp_path) -> None:
    (tmp_path / "project-status.json").write_text("[]", encoding="utf-8")
    with TestClient(create_dashboard_app(tmp_path)) as client:
        response = client.get("/project-status")
    assert response.status_code == 200
    assert 'role="alert"' in response.text


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_loopback_hosts_are_allowed(host: str) -> None:
    assert resolve_loopback_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com"])
def test_non_loopback_hosts_are_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="DASHBOARD_LOOPBACK_ONLY"):
        resolve_loopback_host(host)
