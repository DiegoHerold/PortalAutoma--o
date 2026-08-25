"""Command-line entrypoint for the Portal-side half of the certification
harness. Meant to run inside the backend container, matching how the
existing smoke scripts are invoked:

    docker compose exec backend python -m tools.certification.cli health
    docker compose exec backend python -m tools.certification.cli seed
    docker compose exec backend python -m tools.certification.cli create-execution --scenario echo --agent-id agt_xxx
    docker compose exec backend python -m tools.certification.cli observe --execution-id exe_xxx
    docker compose exec backend python -m tools.certification.cli wait --execution-id exe_xxx --timeout 60

The Windows-side Certification.Cli (automation-agent/tools/Certification.Cli)
shells out to these subcommands for everything that must happen on the
Portal/Python side, instead of re-implementing HTTP calls in C#. This keeps
a single source of truth for the Portal API contract.

Every value that could plausibly be a secret (bearer tokens, registration
tokens) is deliberately kept out of stdout in the JSON responses printed by
this CLI — see docs/certification-harness.md item 78.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any

from tools.certification.api_client import PortalApiClient, PortalApiError
from tools.certification.execution import (
    ExecutionTimeoutError,
    create_certification_execution,
    observe_execution,
    wait_until_status,
    wait_until_terminal,
)
from tools.certification.manifests import CERTIFICATION_PACKAGES
from tools.certification.seed import seed_certification

DEFAULT_BASE_URL = os.environ.get("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1")
DEFAULT_ADMIN_EMAIL = os.environ.get("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local")
DEFAULT_ADMIN_PASSWORD = os.environ.get("CERTIFICATION_ADMIN_PASSWORD", "admin123")
DEFAULT_CERTIFICATION_ROOT = os.environ.get(
    "CERTIFICATION_PACKAGES_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "automation-agent", "certification"),
)


def _client() -> PortalApiClient:
    client = PortalApiClient(base_url=DEFAULT_BASE_URL)
    client.login(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)
    return client


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def cmd_health(_args: argparse.Namespace) -> int:
    result: dict[str, Any] = {"portal_healthy": False, "gateway_healthy": False, "gateway_ready": False}
    try:
        client = PortalApiClient(base_url=DEFAULT_BASE_URL)
        health = client.health()
        result["portal_healthy"] = bool(health.get("status") in ("ok", "healthy", True) or health)
        try:
            gw = client.gateway_health()
            result["gateway_healthy"] = bool(gw)
        except PortalApiError:
            result["gateway_healthy"] = False
        try:
            ready = client.gateway_readiness()
            result["gateway_ready"] = bool(ready)
        except PortalApiError:
            result["gateway_ready"] = False
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        result["error"] = str(exc)
    _print(result)
    return 0 if result["portal_healthy"] else 1


def cmd_seed(_args: argparse.Namespace) -> int:
    client = _client()
    try:
        results = seed_certification(client, DEFAULT_CERTIFICATION_ROOT)
    finally:
        client.close()
    _print({key: asdict(value) for key, value in results.items()})
    return 0


def cmd_create_execution(args: argparse.Namespace) -> int:
    scenario_id = f"certification.{args.scenario}"
    if scenario_id not in {spec.package_id for spec in CERTIFICATION_PACKAGES}:
        print(f"Unknown scenario: {args.scenario}", file=sys.stderr)
        return 2

    client = _client()
    try:
        seeded = seed_certification(client, DEFAULT_CERTIFICATION_ROOT)
        target = seeded[scenario_id]
        parameters = json.loads(args.parameters) if args.parameters else None
        execution = create_certification_execution(
            client,
            target.automation_version_id,
            agent_id=args.agent_id,
            parameters=parameters,
            run_id=args.run_id,
        )
    finally:
        client.close()
    _print(
        {
            "execution_id": execution["execution"]["id"],
            "status": execution["execution"]["status"],
            "automation_version_id": target.automation_version_id,
        }
    )
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    client = _client()
    try:
        observed = observe_execution(client, args.execution_id)
    finally:
        client.close()
    _print(asdict(observed))
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    client = _client()
    try:
        try:
            observed = wait_until_terminal(
                client, args.execution_id, timeout_seconds=args.timeout, poll_interval_seconds=args.interval
            )
        except ExecutionTimeoutError as exc:
            _print({"status": "BLOCKED", "reason": str(exc)})
            return 3
    finally:
        client.close()
    _print(asdict(observed))
    return 0


def cmd_wait_status(args: argparse.Namespace) -> int:
    client = _client()
    try:
        try:
            observed = wait_until_status(
                client,
                args.execution_id,
                statuses=set(args.status),
                timeout_seconds=args.timeout,
                poll_interval_seconds=args.interval,
            )
        except ExecutionTimeoutError as exc:
            _print({"status": "BLOCKED", "reason": str(exc)})
            return 3
    finally:
        client.close()
    _print(asdict(observed))
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    client = _client()
    try:
        result = client.cancel_execution(args.execution_id)
    finally:
        client.close()
    _print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="certification-portal")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health").set_defaults(func=cmd_health)
    sub.add_parser("seed").set_defaults(func=cmd_seed)

    scenario_choices = ["echo", "fail", "timeout", "cancel", "progress", "artifact"]

    create = sub.add_parser("create-execution")
    create.add_argument("--scenario", required=True, choices=scenario_choices)
    create.add_argument("--agent-id", default=None)
    create.add_argument("--run-id", default=None)
    create.add_argument("--parameters", default=None, help="JSON object string")
    create.set_defaults(func=cmd_create_execution)

    observe = sub.add_parser("observe")
    observe.add_argument("--execution-id", required=True)
    observe.set_defaults(func=cmd_observe)

    wait = sub.add_parser("wait")
    wait.add_argument("--execution-id", required=True)
    wait.add_argument("--timeout", type=float, default=120.0)
    wait.add_argument("--interval", type=float, default=1.0)
    wait.set_defaults(func=cmd_wait)

    wait_status = sub.add_parser("wait-status")
    wait_status.add_argument("--execution-id", required=True)
    wait_status.add_argument("--status", action="append", required=True)
    wait_status.add_argument("--timeout", type=float, default=120.0)
    wait_status.add_argument("--interval", type=float, default=1.0)
    wait_status.set_defaults(func=cmd_wait_status)

    cancel = sub.add_parser("cancel")
    cancel.add_argument("--execution-id", required=True)
    cancel.set_defaults(func=cmd_cancel)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
