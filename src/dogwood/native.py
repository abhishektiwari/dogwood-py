from __future__ import annotations

import json
from typing import Any

try:
    from . import _dogwood_native
except ImportError:  # pragma: no cover - exercised only before native build
    _dogwood_native = None


def available() -> bool:
    return _dogwood_native is not None and _dogwood_native.native_available()


def require_available() -> None:
    if not available():
        raise RuntimeError(
            "dogwood native extension is required for schema-backed operations; "
            "run `make develop` or install the maturin-built wheel"
        )


class NativeAuthorizer:
    def __init__(self, policy_source: str, policy_schema_source: str):
        require_available()
        self._inner = _dogwood_native.NativeAuthorizer(policy_source, policy_schema_source)

    def authorize_request(
        self,
        action: str,
        principal: str,
        resource: str,
        input: dict[str, Any],
    ) -> str:
        return self._inner.authorize_request(
            action,
            principal,
            resource,
            json.dumps(input),
        )


def lower_to_cedar(policy_source: str, policy_schema_source: str) -> str:
    require_available()
    return _dogwood_native.lower_to_cedar(policy_source, policy_schema_source)


def cedar_schema(policy_source: str, policy_schema_source: str) -> str:
    require_available()
    return _dogwood_native.cedar_schema(policy_source, policy_schema_source)


def validate_policy(policy_source: str, policy_schema_source: str) -> dict[str, Any]:
    require_available()
    return dict(_dogwood_native.validate_policy(policy_source, policy_schema_source))


def replay(policy_source: str, policy_schema_source: str, trace_source: str) -> str:
    require_available()
    return _dogwood_native.replay(policy_source, policy_schema_source, trace_source)


def authorize_request(
    policy_source: str,
    policy_schema_source: str,
    action: str,
    principal: str,
    resource: str,
    input: dict[str, Any],
) -> str:
    require_available()
    return _dogwood_native.authorize_request(
        policy_source,
        policy_schema_source,
        action,
        principal,
        resource,
        json.dumps(input),
    )
