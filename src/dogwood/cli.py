from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import native
from .policy import LoweredPolicySet, PolicySchema, ServiceSchema, Validator
from .trace import replay_log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dogwood")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check-parse", "validate", "lower", "replay"):
        p = sub.add_parser(name)
        p.add_argument("policies")
        if name != "check-parse":
            p.add_argument("--policy-schema", required=True)
            p.add_argument("--event-schema")
        if name == "replay":
            p.add_argument("--trace", required=True)
    args = parser.parse_args(argv)

    policy_src = _read(args.policies)
    event_schema = _read(args.event_schema) if hasattr(args, "event_schema") and args.event_schema else None
    service = ServiceSchema(event_schema=event_schema)
    if args.command == "check-parse":
        lowered = LoweredPolicySet.from_str(policy_src, service, PolicySchema(""))
        print(f"OK: parsed {lowered.parsed.policy_count()} policy/policies.")
        return 0

    try:
        native.require_available()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    schema = PolicySchema.from_cedarschema_str(_read(args.policy_schema))
    policies = LoweredPolicySet.from_str(policy_src, service, schema)
    if args.command == "validate":
        result = Validator().validate(policies)
        if result.validation_passed():
            print("OK: validation passed with no errors or warnings.")
            return 0
        for error in result.errors:
            print(error, file=sys.stderr)
        return 2
    if args.command == "lower":
        print(policies.as_cedar())
        return 0
    if args.command == "replay":
        print(replay_log(policies, _read(args.trace)))
        return 0
    return 1


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text()


if __name__ == "__main__":
    raise SystemExit(main())
