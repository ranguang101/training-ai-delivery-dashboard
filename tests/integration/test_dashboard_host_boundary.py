"""F-01: the standalone dashboard must only bind loopback addresses."""

import subprocess
import sys
from pathlib import Path

import pytest

from tools.project_dashboard.run import resolve_loopback_host

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "localhost", "::1", "127.0.0.5", "127.255.255.254"],
)
def test_loopback_hosts_are_accepted(host: str) -> None:
    assert resolve_loopback_host(host) == host


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "192.168.1.10", "10.0.0.1", "::", "example.com", ""],
)
def test_non_loopback_hosts_are_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="DASHBOARD_LOOPBACK_ONLY"):
        resolve_loopback_host(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10"])
def test_cli_rejects_non_loopback_startup(host: str) -> None:
    """The operator command must refuse to bind a non-loopback address."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.project_dashboard.run",
            "--host",
            host,
            "--port",
            "8999",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "DASHBOARD_LOOPBACK_ONLY" in result.stderr
    assert host in result.stderr
