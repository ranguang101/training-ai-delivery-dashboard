"""轻量五页看板的数据源、页面入口和文件变更刷新回归。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration._dashboard_fixtures import make_panel_root
from tools.project_dashboard.main import create_dashboard_app

LINE_ID = "fixture-line"


def _status(summary: str = "Fixture summary") -> dict:
    return {
        "project_name": "Synthetic dashboard project",
        "overall_status": "in_progress",
        "progress_percent": 42,
        "current_focus": "Fixture delivery direction",
        "summary": summary,
        "last_updated": "2026-08-26T10:00:00+08:00",
        "delivery_lines": [
            {
                "id": LINE_ID,
                "name": "Synthetic delivery line",
                "summary": "Fixture line summary",
                "status": "in_progress",
                "open_blockers": [],
            }
        ],
        "product_roadmap": {
            "baseline": "Fixture product baseline",
            "source_document": "docs/internal/fixture-baseline.md",
            "current_position": "Fixture roadmap position",
            "versions": [
                {
                    "code": "fixture-v1",
                    "title": "Fixture version",
                    "status": "planned",
                    "scope": "Fixture scope",
                    "next_gate": "Fixture next gate",
                }
            ],
        },
    }


def _client(root: Path) -> TestClient:
    return TestClient(create_dashboard_app(root))


def test_five_lightweight_pages_and_api_share_one_source(tmp_path: Path) -> None:
    root = make_panel_root(tmp_path, project_status=_status(), with_templates=True)
    routes = {
        "/project-status": "overview",
        "/project-status/product": "product",
        "/project-status/frontend": "frontend",
        "/project-status/development": "development",
        "/project-status/tests": "testing",
    }

    with _client(root) as client:
        for route, page in routes.items():
            response = client.get(f"{route}?line={LINE_ID}")
            assert response.status_code == 200
            assert f'data-dashboard-page="{page}"' in response.text

            api = client.get(
                "/api/v1/project-status/lightweight",
                params={"page": page, "line": LINE_ID},
            )
            assert api.status_code == 200
            data = api.json()["data"]
            assert data["page"] == page
            assert data["project"]["name"] == "Synthetic dashboard project"
            assert data["selected_line"]["delivery_line_id"] == LINE_ID

        product = client.get(
            "/api/v1/project-status/lightweight", params={"page": "product"}
        ).json()["data"]
        assert product["data"]["source_document"] == "产品基线来源已登记"


def test_quality_page_is_explicitly_unlinked_without_quality_data(tmp_path: Path) -> None:
    root = make_panel_root(tmp_path, project_status=_status(), with_templates=True)

    with _client(root) as client:
        response = client.get(
            "/api/v1/project-status/lightweight",
            params={"page": "testing"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["data"]["state"] == "unlinked"
    assert data["data"]["formal_cases"] is None
    assert data["warnings"] == [
        {"code": "DASHBOARD_QUALITY_UNLINKED", "safe_message": "质量统计待关联"}
    ]


def test_file_change_invalidates_process_cache_for_lightweight_api(tmp_path: Path) -> None:
    root = make_panel_root(tmp_path, project_status=_status("Before"), with_templates=True)
    status_path = root / "project-status.json"

    with _client(root) as client:
        first = client.get("/api/v1/project-status/lightweight", params={"page": "overview"})
        assert first.json()["data"]["data"]["summary"] == "Before"

        status_path.write_text(
            json.dumps(_status("After"), ensure_ascii=False), encoding="utf-8"
        )
        second = client.get("/api/v1/project-status/lightweight", params={"page": "overview"})

    assert second.status_code == 200
    assert second.json()["data"]["data"]["summary"] == "After"


def test_unknown_page_or_delivery_line_is_not_silently_filled(tmp_path: Path) -> None:
    root = make_panel_root(tmp_path, project_status=_status(), with_templates=True)

    with _client(root) as client:
        bad_page = client.get(
            "/api/v1/project-status/lightweight", params={"page": "unknown"}
        )
        bad_line = client.get(
            "/api/v1/project-status/lightweight",
            params={"page": "overview", "line": "not-registered"},
        )

    assert bad_page.status_code == 404
    assert bad_line.status_code == 404
