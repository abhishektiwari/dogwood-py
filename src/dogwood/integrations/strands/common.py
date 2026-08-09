from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

InputMapper = Callable[[Any], dict[str, Any]]
IdentityResolver = Callable[[Any], str]


def default_tool_input(event: Any) -> dict[str, Any]:
    """Build Dogwood request input from a Strands BeforeToolCallEvent."""
    tool_use = _tool_use(event)
    return {
        "tool": _tool_value(tool_use, "name", ""),
        "input": _tool_value(tool_use, "input", {}),
        "toolUseId": _tool_value(
            tool_use,
            "toolUseId",
            _tool_value(tool_use, "tool_use_id", ""),
        ),
    }


def default_principal(event: Any) -> str:
    """Resolve the Cedar principal from Strands invocation state."""
    state = getattr(event, "invocation_state", {}) or {}
    return str(state.get("principal", 'Drupe::OAuthUser::"agent"'))


def default_resource(event: Any) -> str:
    """Resolve the Cedar resource from Strands invocation state."""
    state = getattr(event, "invocation_state", {}) or {}
    return str(state.get("resource", 'Drupe::Gateway::"agent"'))


def _authorize_event(policy_hook: Any, event: Any) -> Any:
    return policy_hook.authorizer.authorize_request(
        policy_hook.action,
        _resolve(policy_hook.principal, event),
        _resolve(policy_hook.resource, event),
        policy_hook.input_mapper(event),
    )


def _is_allowed(decision: Any) -> bool:
    return decision == "Allow"


def _tool_use(event: Any) -> Any:
    return getattr(event, "tool_use", {})


def _tool_value(tool_use: Any, key: str, default: Any) -> Any:
    if isinstance(tool_use, Mapping):
        return tool_use.get(key, default)
    return getattr(tool_use, key, default)


def _resolve(value: str | IdentityResolver, event: Any) -> str:
    if callable(value):
        return value(event)
    return value


__all__ = [
    "IdentityResolver",
    "InputMapper",
    "default_principal",
    "default_resource",
    "default_tool_input",
]
