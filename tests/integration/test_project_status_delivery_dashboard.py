import copy
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from fastapi.testclient import TestClient

from app.services.project_status import PROJECT_STATUS_PATH, load_project_status
from tools.project_dashboard.main import create_dashboard_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_handle:
        socket_handle.bind(("127.0.0.1", 0))
        return int(socket_handle.getsockname()[1])


def test_safe_delivery_dashboard_exposes_only_declared_safe_projection(monkeypatch):
    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")

    with TestClient(create_dashboard_app()) as client:
        response = client.get("/api/v1/project-status/dashboard")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["delivery_lines"]) == 2
    line = payload["delivery_lines"][0]
    assert line["delivery_track"] == "management_operations_foundation"
    assert line["delivery_status"] == "integration"
    assert line["evidence_level"] == "D1"
    assert line["verified_at"] == "2026-08-11"
    assert line["updated_at"] == "2026-08-11T00:00:00+08:00"
    assert line["source_role"] == "product"
    assert line["source_role_label"] == "产品负责人"
    assert line["contract_state"]["status"] == "frozen"
    assert line["candidate_version"]["status"] == "not_fixed"
    assert line["runtime_gate"]["status"] == "not_assessed"
    assert payload["workspace_refs"]["roles"]["development"] == [
        "mvp-a-management-foundation",
        "mvp-b-daily-record-closure",
    ]

    evidence = line["evidence_links"][0]
    assert "document_path" not in evidence
    assert evidence["href"].startswith(
        "/api/v1/project-status/dashboard/delivery-lines/"
    )
    assert evidence["verified_at"] == "2026-08-11"
    assert evidence["source_role"] == "product"
    assert evidence["source_role_label"] == "产品负责人"
    assert "D:" not in json.dumps(payload, ensure_ascii=False)


def test_dashboard_page_has_a_safe_server_rendered_delivery_fallback(monkeypatch):
    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")

    with TestClient(create_dashboard_app()) as client:
        response = client.get("/project-status")

    assert response.status_code == 200
    assert "data-delivery-server-fallback" in response.text
    assert "MVP-A · 管理运营底座" in response.text
    assert "MVP-B · 教师每日学情闭环" in response.text
    assert "D1 · 模块范围已确认" in response.text
    assert "已冻结" in response.text
    assert "not_frozen" not in response.text
    assert "D:/" not in response.text


def test_dashboard_page_neutralizes_evidence_links_failing_the_whitelist(monkeypatch):
    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")
    import app.routers.project_status as router_module
    from app.services.project_status import (
        build_delivery_dashboard_view as real_build_view,
    )

    def tampered_view(project, *, project_root=PROJECT_ROOT):
        view = real_build_view(project, project_root=project_root)
        view["delivery_lines"][0]["evidence_links"][0]["href"] = (
            "file:///D:/private/report.md"
        )
        return view

    monkeypatch.setattr(router_module, "build_delivery_dashboard_view", tampered_view)

    with TestClient(create_dashboard_app()) as client:
        response = client.get("/project-status")

    assert response.status_code == 200
    assert "证据链接不可用：未通过安全白名单校验。" in response.text
    assert 'href="file:///D:/private/report.md"' not in response.text
    # 其余证据仍按白名单渲染为可点击的受控证据入口
    assert (
        "/api/v1/project-status/dashboard/delivery-lines/"
        "mvp-a-management-foundation/evidence/" in response.text
    )


def test_safe_evidence_drill_down_does_not_return_raw_document_content(monkeypatch):
    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")

    with TestClient(create_dashboard_app()) as client:
        response = client.get(
            "/api/v1/project-status/dashboard/delivery-lines/"
            "mvp-b-daily-record-closure/evidence/PRD-CHANGE-20260811-002"
        )

    assert response.status_code == 200
    evidence = response.json()["data"]
    assert evidence["id"] == "PRD-CHANGE-20260811-002"
    assert evidence["evidence_level"] == "D1"
    assert "document_path" not in evidence
    assert "content" not in evidence


def test_delivery_line_rejects_unsafe_document_path_and_unverified_d5(tmp_path):
    payload = json.loads(PROJECT_STATUS_PATH.read_text(encoding="utf-8"))
    unsafe_path_payload = copy.deepcopy(payload)
    unsafe_path_payload["delivery_lines"][0]["evidence_links"][0]["document_path"] = (
        "D:/private/report.md"
    )
    unsafe_path = tmp_path / "unsafe-path.json"
    unsafe_path.write_text(json.dumps(unsafe_path_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="safe docs-relative path"):
        load_project_status(unsafe_path)

    unverified_payload = copy.deepcopy(payload)
    unverified_payload["delivery_lines"][0]["evidence_level"] = "D5"
    unverified_path = tmp_path / "unverified-d5.json"
    unverified_path.write_text(json.dumps(unverified_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="requires verified gates"):
        load_project_status(unverified_path)


def test_standalone_dashboard_process_serves_delivery_contract():
    """Verify the operator command starts the management panel without app.main."""
    port = _available_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tools.project_dashboard.run",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/api/v1/project-status/dashboard"
    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                with urlopen(url, timeout=1) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)

        assert payload["success"] is True
        assert payload["data"]["delivery_lines"][0]["evidence_level"] == "D1"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_standalone_dashboard_can_inject_a_safe_404_for_ui_recovery_testing():
    port = _available_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tools.project_dashboard.run",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--test-fault",
            "dashboard_404",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/api/v1/project-status/dashboard"
    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                with urlopen(url, timeout=1):  # noqa: S310
                    pass
            except HTTPError as exc:
                assert exc.code == 404
                assert json.loads(exc.read().decode("utf-8"))["detail"] == (
                    "DASHBOARD_TEST_NOT_FOUND"
                )
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
    finally:
        process.terminate()
        process.wait(timeout=5)
