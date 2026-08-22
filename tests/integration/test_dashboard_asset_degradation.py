"""F-05: corrupt assets degrade safely and never take the dashboard down."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import test_management
from tests.integration._dashboard_fixtures import (
    make_panel_root,
    minimal_project_status,
    write_valid_run,
)
from tools.project_dashboard.main import create_dashboard_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _root_with_stage(tmp_path) -> Path:
    root = make_panel_root(
        tmp_path,
        project_status=minimal_project_status(
            stages=[{"code": "P1", "title": "账号与权限", "requirements_count": 0}]
        ),
        with_templates=True,
    )
    cases_dir = root / "docs" / "testing" / "cases"
    cases_dir.mkdir(parents=True)
    (cases_dir / "P1.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": f"P1-TC-{number:03}",
                        "title": f"接口契约 {number}",
                        "type": "api",
                        "priority": "P0",
                        "automation_status": "automated",
                        "automation": {"framework": "pytest"},
                    }
                    for number in range(1, 4)
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def test_corrupt_defects_json_degrades_quality_page(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    write_valid_run(root)
    defects_path = root / "docs" / "testing" / "defects.json"
    defects_path.parent.mkdir(parents=True, exist_ok=True)
    defects_path.write_text("{corrupt json", encoding="utf-8")

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert 'role="alert"' in quality.text
    assert "缺陷清单无法读取" in quality.text


def test_corrupt_integrations_json_degrades_quality_page(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    write_valid_run(root)
    integrations_path = root / "docs" / "testing" / "integrations.json"
    integrations_path.parent.mkdir(parents=True, exist_ok=True)
    integrations_path.write_text("[not valid json", encoding="utf-8")

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert "测试接入清单无法读取" in quality.text


def test_corrupt_summary_json_does_not_break_overview_or_quality(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    run_dir = root / "reports" / "test-runs" / "RUN-P1-20260809-000003"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text("{broken", encoding="utf-8")

    summary = test_management.stage_test_summary("P1", project_root=root)
    assert summary["status"] == "ready"
    assert summary["warnings"]

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert 'role="alert"' in quality.text
    assert "无效或非受控的测试运行记录" in quality.text


def test_corrupt_stage_cases_file_degrades_overview(tmp_path) -> None:
    root = make_panel_root(
        tmp_path,
        project_status=minimal_project_status(
            stages=[{"code": "P1", "title": "账号与权限", "requirements_count": 0}]
        ),
        with_templates=True,
    )
    cases_path = root / "docs" / "testing" / "cases" / "P1.json"
    cases_path.parent.mkdir(parents=True)
    cases_path.write_text("{{{{", encoding="utf-8")

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert "正式 Case 清单无法读取" in quality.text


def test_corrupt_automation_index_degrades_listing(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    index_path = root / "docs" / "testing" / "automation-run-index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("not json at all", encoding="utf-8")

    with TestClient(create_dashboard_app(root)) as client:
        response = client.get("/api/v1/project-status/test-automation")

    assert response.status_code == 200
    assert response.json()["data"]["runs"] == []
    assert response.json()["data"]["warnings"] == [
        "辅助自动化运行摘要无法读取；当前不显示任何辅助执行结果。"
    ]


def test_corrupt_candidate_case_assets_never_break_case_design(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    tasks_path = root / "docs" / "testing" / "case-generation" / "case-generation-runs.json"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text("{broken", encoding="utf-8")

    with TestClient(create_dashboard_app(root)) as client:
        listing = client.get("/project-status/tests/case-design")
        data = client.get("/api/v1/project-status/tests/case-design")

    assert listing.status_code == 200
    assert 'role="alert"' in listing.text
    assert data.status_code == 200
    assert data.json()["data"]["tasks"] == []


def test_corrupt_candidate_case_detail_asset_shows_safe_summary(tmp_path) -> None:
    root = make_panel_root(tmp_path)
    tasks_dir = root / "docs" / "testing" / "case-generation"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "detail-broken.json").write_text("{broken", encoding="utf-8")
    (tasks_dir / "case-generation-runs.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "id": "CASE-GEN-P3-001",
                        "stage": "P3",
                        "title": "候选设计任务",
                        "status": "待人工评审",
                        "asset": "detail-broken.json",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    task = test_management.load_case_design_task("CASE-GEN-P3-001", project_root=root)
    assert task["warning"] == "生成任务详情资产无法读取，已仅展示安全摘要。"


def test_corrupt_document_status_json_degrades_document_center(monkeypatch, tmp_path) -> None:
    """Business document center must degrade on a corrupt document-status.json."""
    from app.main import app
    from app.services import document_catalog

    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "doc-status.db"))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "document-status.json").write_text("{corrupt", encoding="utf-8")
    good = docs_dir / "owner" / "good.md"
    good.parent.mkdir(parents=True)
    good.write_text("# 状态降级文档\n\n可读内容。", encoding="utf-8")
    monkeypatch.setattr(document_catalog, "DOCUMENTS_DIR", docs_dir)

    catalog = document_catalog.build_document_catalog()
    assert catalog["total"] == 1

    with TestClient(app) as client:
        response = client.get("/project-status/documents")

    assert response.status_code == 200
    assert "状态降级文档" in response.text


def test_unreadable_markdown_file_degrades_document_center(monkeypatch, tmp_path) -> None:
    from app.main import app
    from app.services import document_catalog

    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "unreadable-doc.db"))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "document-status.json").write_text("{}", encoding="utf-8")
    unreadable = docs_dir / "internal" / "broken.md"
    unreadable.parent.mkdir(parents=True)
    unreadable.write_bytes(b"\xff\xfe\x00\x9d broken bytes")
    good = docs_dir / "owner" / "good.md"
    good.parent.mkdir(parents=True)
    good.write_text("# 正常文档\n\n可读内容。", encoding="utf-8")
    monkeypatch.setattr(document_catalog, "DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr(
        document_catalog, "DOCUMENT_STATUS_PATH", docs_dir / "document-status.json"
    )

    catalog = document_catalog.build_document_catalog()
    assert any(item["title"] == "正常文档" for item in catalog["documents"])
    assert any("无法读取的项目文档" in warning for warning in catalog["warnings"])

    with TestClient(app) as client:
        response = client.get("/project-status/documents")

    assert response.status_code == 200
    assert "部分文档数据已安全降级" in response.text
    assert "正常文档" in response.text


def test_summary_json_with_list_root_degrades_safely(tmp_path) -> None:
    """R1-C02: valid JSON with a non-object root must not raise AttributeError."""
    root = _root_with_stage(tmp_path)
    run_dir = root / "reports" / "test-runs" / "RUN-P1-20260809-000004"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text("[]", encoding="utf-8")

    summary = test_management.stage_test_summary("P1", project_root=root)
    assert summary["status"] == "ready"
    assert any("无效或非受控的测试运行记录" in warning for warning in summary["warnings"])

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert "无效或非受控的测试运行记录" in quality.text


def test_summary_json_with_string_root_degrades_safely(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    run_dir = root / "reports" / "test-runs" / "RUN-P1-20260809-000005"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text('"just a string"', encoding="utf-8")

    summary = test_management.stage_test_summary("P1", project_root=root)
    assert summary["status"] == "ready"

    with TestClient(create_dashboard_app(root)) as client:
        assert client.get("/project-status").status_code == 200
        assert client.get("/project-status/tests").status_code == 200


def test_defects_json_with_list_root_degrades_safely(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    defects_path = root / "docs" / "testing" / "defects.json"
    defects_path.parent.mkdir(parents=True, exist_ok=True)
    defects_path.write_text("[]", encoding="utf-8")

    assert test_management.load_defects(project_root=root) == []
    summary = test_management.stage_test_summary("P1", project_root=root)
    assert any("缺陷清单格式无效" in warning for warning in summary["warnings"])

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert "缺陷清单格式无效" in quality.text


def test_integrations_json_with_list_root_degrades_safely(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    integrations_path = root / "docs" / "testing" / "integrations.json"
    integrations_path.parent.mkdir(parents=True, exist_ok=True)
    integrations_path.write_text("[]", encoding="utf-8")

    assert test_management.load_test_integrations(project_root=root) == []
    summary = test_management.stage_test_summary("P1", project_root=root)
    assert any("测试接入清单格式无效" in warning for warning in summary["warnings"])

    with TestClient(create_dashboard_app(root)) as client:
        assert client.get("/project-status").status_code == 200
        assert client.get("/project-status/tests").status_code == 200


def test_cases_json_with_list_root_degrades_overview(tmp_path) -> None:
    root = _root_with_stage(tmp_path)
    (root / "docs" / "testing" / "cases" / "P1.json").write_text(
        "[]", encoding="utf-8"
    )

    summary = test_management.stage_test_summary("P1", project_root=root)
    assert summary["total"] == 0
    assert any("正式 Case 清单格式无效" in warning for warning in summary["warnings"])

    with TestClient(create_dashboard_app(root)) as client:
        overview = client.get("/project-status")
        quality = client.get("/project-status/tests")

    assert overview.status_code == 200
    assert quality.status_code == 200
    assert "正式 Case 清单格式无效" in quality.text


def test_document_status_json_with_list_root_degrades(monkeypatch, tmp_path) -> None:
    from app.main import app
    from app.services import document_catalog

    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "doc-status-list.db"))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "document-status.json").write_text("[]", encoding="utf-8")
    good = docs_dir / "owner" / "good.md"
    good.parent.mkdir(parents=True)
    good.write_text("# 列表根降级文档\n\n可读内容。", encoding="utf-8")
    monkeypatch.setattr(document_catalog, "DOCUMENTS_DIR", docs_dir)

    catalog = document_catalog.build_document_catalog()
    assert any("文档状态清单格式无效" in warning for warning in catalog["warnings"])
    assert any(item["title"] == "列表根降级文档" for item in catalog["documents"])

    with TestClient(app) as client:
        response = client.get("/project-status/documents")

    assert response.status_code == 200
    assert "部分文档数据已安全降级" in response.text


def test_document_status_entry_with_non_object_value_degrades(monkeypatch, tmp_path) -> None:
    from app.main import app
    from app.services import document_catalog

    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "doc-status-entry.db"))
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "document-status.json").write_text(
        json.dumps({"documents": {"owner/good.md": "not-an-object"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    good = docs_dir / "owner" / "good.md"
    good.parent.mkdir(parents=True)
    good.write_text("# 条目降级文档\n\n可读内容。", encoding="utf-8")
    monkeypatch.setattr(document_catalog, "DOCUMENTS_DIR", docs_dir)

    catalog = document_catalog.build_document_catalog()
    assert any(item["title"] == "条目降级文档" for item in catalog["documents"])
    assert all(
        item["status"] in {"current", "historical", "superseded", "unclassified"}
        for item in catalog["documents"]
    )

    with TestClient(app) as client:
        assert client.get("/project-status/documents").status_code == 200
