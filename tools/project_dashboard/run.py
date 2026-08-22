"""Run the standalone local project dashboard on its own port."""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path

import uvicorn

from tools.project_dashboard.main import create_dashboard_app

LOOPBACK_NAMES = frozenset({"127.0.0.1", "localhost", "::1"})


def resolve_loopback_host(host: str) -> str:
    """Allow only explicit loopback addresses; reject wildcard and LAN hosts."""
    candidate = host.strip()
    if candidate in LOOPBACK_NAMES:
        return candidate
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise ValueError(
            f"DASHBOARD_LOOPBACK_ONLY: --host must be a loopback address "
            f"(127.0.0.1, ::1 or localhost); got {host!r}"
        ) from exc
    if not address.is_loopback:
        raise ValueError(
            f"DASHBOARD_LOOPBACK_ONLY: --host must be a loopback address "
            f"(127.0.0.1, ::1 or localhost); got {host!r}"
        )
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local project dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository whose project-status.json, docs and reports are displayed",
    )
    parser.add_argument(
        "--test-fault",
        choices=["dashboard_404"],
        help="Independent dashboard QA only; never use for normal operator startup.",
    )
    args = parser.parse_args()
    try:
        host = resolve_loopback_host(args.host)
    except ValueError as exc:
        parser.error(str(exc))
    uvicorn.run(
        create_dashboard_app(args.project_root, dashboard_test_fault=args.test_fault),
        host=host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
