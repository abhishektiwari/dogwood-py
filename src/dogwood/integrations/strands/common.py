from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any

from dogwood.enforcement import EnforcementMode, is_allowed_decision, is_enforced, normalize_mode

InputMapper = Callable[[Any], dict[str, Any]]
ActionResolver = Callable[[Any], str]
IdentityResolver = Callable[[Any], str]
LifecycleEvent = str

ALL_LIFECYCLE_EVENTS: tuple[LifecycleEvent, ...] = (
    "before_invocation",
    "after_invocation",
    "message_added",
    "before_model_call",
    "after_model_call",
    "before_tool_call",
    "after_tool_call",
)


def default_tool_input(event: Any) -> dict[str, Any]:
    """Build Dogwood tool-call input from a Strands tool event.

    The default input shape is framework-neutral so the same Dogwood policy can
    be reused by future agent integrations. It works with a generic
    ``CallTool`` action and with schemas that map each tool name to a concrete
    Cedar action:

    ``{"tool": name, "input": tool_input, "toolUseId": id}``
    """
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


def default_lifecycle_input(event: Any) -> dict[str, Any]:
    """Build Dogwood input from any supported Strands lifecycle event.

    This mapper intentionally keeps the payload small and JSON-safe. It records
    the lifecycle name plus a few stable fields that policies commonly need.
    Tool-call events still use :func:`default_tool_input` by default.
    """
    lifecycle = getattr(event, "dogwood_lifecycle", event.__class__.__name__)
    payload: dict[str, Any] = {"lifecycle": _snake_lifecycle(str(lifecycle))}
    invocation_state = getattr(event, "invocation_state", None)
    if invocation_state:
        payload["invocationState"] = _json_safe(invocation_state)
    for name in (
        "projected_input_tokens",
        "result",
        "message",
        "messages",
        "model",
        "stop_reason",
        "error",
    ):
        if hasattr(event, name):
            payload[name] = _json_safe(getattr(event, name))
    return payload


def default_principal(event: Any) -> str:
    """Resolve the Cedar principal from Strands ``invocation_state``."""
    state = getattr(event, "invocation_state", {}) or {}
    return str(state.get("principal", 'Agent::OAuthUser::"agent"'))


def default_resource(event: Any) -> str:
    """Resolve the Cedar resource from Strands ``invocation_state``."""
    state = getattr(event, "invocation_state", {}) or {}
    return str(state.get("resource", 'Agent::Gateway::"agent"'))


def _authorize_event(policy_hook: Any, event: Any) -> Any:
    return policy_hook.authorizer.authorize_request(
        _resolve(policy_hook.action, event),
        _resolve(policy_hook.principal, event),
        _resolve(policy_hook.resource, event),
        policy_hook.input_mapper(event),
    )


def _event_enabled(enabled: Collection[str] | str, lifecycle: str) -> bool:
    if enabled == "all":
        return lifecycle in ALL_LIFECYCLE_EVENTS
    return lifecycle in enabled


def _is_allowed(decision: Any) -> bool:
    return is_allowed_decision(decision)


def _is_enforced(mode: EnforcementMode) -> bool:
    return is_enforced(mode)


def _normalize_mode(mode: str) -> EnforcementMode:
    return normalize_mode(mode)


def _record_decision(event: Any, decision: Any, mode: EnforcementMode) -> None:
    setattr(event, "dogwood_decision", str(decision))
    setattr(event, "dogwood_enforcement_mode", mode)
    setattr(event, "dogwood_would_have_denied", mode == "log_only" and not _is_allowed(decision))


def _tool_use(event: Any) -> Any:
    return getattr(event, "tool_use", {})


def _tool_value(tool_use: Any, key: str, default: Any) -> Any:
    if isinstance(tool_use, Mapping):
        return tool_use.get(key, default)
    return getattr(tool_use, key, default)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _snake_lifecycle(value: str) -> str:
    if "_" in value:
        return value
    out = []
    for index, char in enumerate(value):
        if char.isupper() and index:
            out.append("_")
        out.append(char.lower())
    return "".join(out).removesuffix("_event")


def _resolve(value: str | Callable[[Any], str], event: Any) -> str:
    if callable(value):
        return value(event)
    return value


__all__ = [
    "ActionResolver",
    "EnforcementMode",
    "IdentityResolver",
    "InputMapper",
    "ALL_LIFECYCLE_EVENTS",
    "LifecycleEvent",
    "default_principal",
    "default_resource",
    "default_lifecycle_input",
    "default_tool_input",
]
