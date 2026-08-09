from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dogwood import native
from dogwood.integrations.strands.common import (
    IdentityResolver,
    InputMapper,
    _authorize_event,
    _is_allowed,
    default_principal,
    default_resource,
    default_tool_input,
)


@dataclass
class StrandsPolicyHook:
    """Authorize Strands tool calls with a Dogwood native authorizer.

    Register instances of this class as Strands hooks for ``BeforeToolCallEvent``.
    If Dogwood denies the request, the hook sets ``event.cancel_tool`` with a
    denial message, which prevents Strands from invoking the tool.
    """

    authorizer: native.NativeAuthorizer
    action: str = "Drupe::Action::CallTool"
    principal: str | IdentityResolver = default_principal
    resource: str | IdentityResolver = default_resource
    input_mapper: InputMapper = default_tool_input
    deny_message: str = "Dogwood policy denied this tool call."

    def __call__(self, event: Any) -> None:
        if not _is_allowed(_authorize_event(self, event)):
            event.cancel_tool = self.deny_message


def before_tool_call_hook(
    policy_source: str,
    policy_schema_source: str,
    *,
    event_schema_source: str | None = None,
    action: str = "Drupe::Action::CallTool",
    principal: str | IdentityResolver = default_principal,
    resource: str | IdentityResolver = default_resource,
    input_mapper: InputMapper = default_tool_input,
    deny_message: str = "Dogwood policy denied this tool call.",
) -> StrandsPolicyHook:
    """Create a Strands ``BeforeToolCallEvent`` hook backed by Dogwood.

    The native Dogwood authorizer is persistent, so policy parsing and lowering
    happen once when this hook is constructed.
    """
    return _build_policy_hook(
        policy_source,
        policy_schema_source,
        event_schema_source=event_schema_source,
        action=action,
        principal=principal,
        resource=resource,
        input_mapper=input_mapper,
        deny_message=deny_message,
    )


def attach_before_tool_call_hook(agent: Any, hook: StrandsPolicyHook) -> None:
    """Attach a Dogwood policy hook to a Strands agent.

    This imports Strands only when called, keeping ``dogwood-py`` free of a hard
    Strands dependency.
    """
    try:
        from strands.hooks import BeforeToolCallEvent
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError(
            "Strands integration requires the optional `strands-agents` package"
        ) from exc

    if hasattr(agent, "hooks") and hasattr(agent.hooks, "add_callback"):
        agent.hooks.add_callback(BeforeToolCallEvent, hook)
        return

    if hasattr(agent, "add_hook"):
        agent.add_hook(hook, BeforeToolCallEvent)
        return

    raise TypeError("agent does not expose a supported Strands hook registration API")


def _build_policy_hook(
    policy_source: str | None,
    policy_schema_source: str | None,
    *,
    event_schema_source: str | None = None,
    authorizer: native.NativeAuthorizer | None = None,
    action: str,
    principal: str | IdentityResolver,
    resource: str | IdentityResolver,
    input_mapper: InputMapper,
    deny_message: str,
) -> StrandsPolicyHook:
    if authorizer is None:
        if policy_source is None or policy_schema_source is None:
            raise TypeError(
                "policy_source and policy_schema_source are required when "
                "authorizer is not supplied"
            )
        authorizer = native.NativeAuthorizer(
            policy_source,
            policy_schema_source,
            event_schema_source,
        )

    return StrandsPolicyHook(
        authorizer=authorizer,
        action=action,
        principal=principal,
        resource=resource,
        input_mapper=input_mapper,
        deny_message=deny_message,
    )


__all__ = [
    "StrandsPolicyHook",
    "attach_before_tool_call_hook",
    "before_tool_call_hook",
]
