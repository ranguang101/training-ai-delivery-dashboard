"""Read-only page checks for the auxiliary UI automation workspace."""

from fastapi.testclient import TestClient

from tools.project_dashboard.main import create_dashboard_app


def test_auxiliary_automation_pages_use_only_safe_summary_routes() -> None:
    with TestClient(create_dashboard_app()) as client:
        center = client.get("/project-status/tests")
        listing = client.get("/project-status/tests/automation")
        detail = client.get(
            "/project-status/tests/automation/runs/AUX-P1-TC-021-20260815-001"
        )
        missing = client.get("/project-status/tests/automation/runs/AUX-P1-TC-021-999")

    assert center.status_code == 200
    assert 'data-testid="test-automation-entry"' in center.text
    assert "不计入正式 Case、执行、通过、缺陷或版本准出统计" in center.text
    assert listing.status_code == 200
    assert "辅助 UI 自动化：先辅助复核，不替代正式结论" in listing.text
    assert 'data-test-automation-content' in listing.text
    assert detail.status_code == 200
    assert "本次为辅助自动化执行，不更新正式 Case 状态" in detail.text
    assert 'data-test-automation-run-id="AUX-P1-TC-021-20260815-001"' in detail.text
    assert missing.status_code == 404
    for page in (center.text, listing.text, detail.text):
        assert "D:\\wta" not in page
        assert "report.json" not in page
