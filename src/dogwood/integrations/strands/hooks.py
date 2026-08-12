from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dogwood import native
from dogwood.integrations.strands.common import (
    ActionResolver,
    ALL_LIFECYCLE_EVENTS,
    EnforcementMode,
    IdentityResolver,
    InputMapper,
    _authorize_event,
    _event_enabled,
    _is_enforced,
    _is_allowed,
    _normalize_mode,
    _record_decision,
    default_lifecycle_input,
    default_principal,
    default_resource,
    default_tool_input,
)

DEFAULT_LIFECYCLE_EVENTS: tuple[str, ...] = ("before_tool_call",)

_CANCEL_ATTRS = {
    "before_invocation": "cancel",
    "before_model_call": "cancel",
    "before_tool_call": "cancel_tool",
}


@dataclass
class StrandsPolicyHook:
    """Low-level Strands hook backed by a Dogwood native authorizer.

    This is the lowest-level integration surface. Register it for
    ``BeforeToolCallEvent`` when you want direct hook behavior instead of a
    Strands plugin or intervention.

    If Dogwood denies the request, the hook sets ``event.cancel_tool`` with
    ``deny_message``. Strands then skips the selected tool.

    Use this class when you need direct hook registration. Otherwise prefer
    :class:`DogwoodIntervention` for typed decisions or :class:`DogwoodPlugin`
    for Strands plugin auto-discovery.
    """

    authorizer: native.NativeAuthorizer
    action: str | ActionResolver = "Agent::Action::CallTool"
    principal: str | IdentityResolver = default_principal
    resource: str | IdentityResolver = default_resource
    input_mapper: InputMapper = default_tool_input
    mode: EnforcementMode = "enforce"
    deny_message: str = "Dogwood policy denied this tool call."

    def __call__(self, event: Any) -> None:
        """Authorize one tool event.

        ``action`` may be a fixed Cedar action or a resolver callback that
        derives the action from the Strands tool event.
        """
        decision = _authorize_event(self, event)
        self.mode = _normalize_mode(self.mode)
        _record_decision(event, decision, self.mode)
        if _is_enforced(self.mode) and not _is_allowed(decision):
            event.cancel_tool = self.deny_message


@dataclass
class StrandsLifecyclePolicyHook:
    """Lifecycle-aware Strands hook backed by Dogwood authorization.

    ``StrandsLifecyclePolicyHook`` supports every primary Strands agent
    lifecycle event. It is opt-in per lifecycle to avoid accidentally applying
    a tool policy to invocation or model events.

    Before-events can be cancelled when Dogwood denies. After-events are
    observed by calling Dogwood and then continue, because Strands does not
    support hard denial after work has already happened.
    """

    authorizer: native.NativeAuthorizer
    action: str | ActionResolver = "Agent::Action::CallTool"
    principal: str | IdentityResolver = default_principal
    resource: str | IdentityResolver = default_resource
    tool_input_mapper: InputMapper = default_tool_input
    lifecycle_input_mapper: InputMapper = default_lifecycle_input
    lifecycle_events: tuple[str, ...] | str = DEFAULT_LIFECYCLE_EVENTS
    mode: EnforcementMode = "enforce"
    deny_message: str = "Dogwood policy denied this lifecycle event."

    def handle(self, lifecycle: str, event: Any) -> str:
        """Evaluate a lifecycle event and return the Dogwood decision string."""
        setattr(event, "dogwood_lifecycle", lifecycle)
        if not _event_enabled(self.lifecycle_events, lifecycle):
            return "Skipped"
        decision = _authorize_event(self._policy_view(lifecycle), event)
        self.mode = _normalize_mode(self.mode)
        _record_decision(event, decision, self.mode)
        if _is_enforced(self.mode) and not _is_allowed(decision) and lifecycle in _CANCEL_ATTRS:
            setattr(event, _CANCEL_ATTRS[lifecycle], self.deny_message)
        return str(decision)

    def _policy_view(self, lifecycle: str) -> Any:
        mapper = self.tool_input_mapper if "tool_call" in lifecycle else self.lifecycle_input_mapper
        return _PolicyView(
            authorizer=self.authorizer,
            action=self.action,
            principal=self.principal,
            resource=self.resource,
            input_mapper=mapper,
        )


@dataclass(frozen=True)
class _PolicyView:
    authorizer: native.NativeAuthorizer
    action: str | ActionResolver
    principal: str | IdentityResolver
    resource: str | IdentityResolver
    input_mapper: InputMapper


def before_tool_call_hook(
    policy_source: str,
    policy_schema_source: str,
    *,
    event_schema_source: str | None = None,
    action: str | ActionResolver = "Agent::Action::CallTool",
    principal: str | IdentityResolver = default_principal,
    resource: str | IdentityResolver = default_resource,
    input_mapper: InputMapper = default_tool_input,
    mode: EnforcementMode = "enforce",
    deny_message: str = "Dogwood policy denied this tool call.",
) -> StrandsPolicyHook:
    """Create a low-level ``BeforeToolCallEvent`` hook backed by Dogwood.

    The native Dogwood authorizer is persistent, so policy parsing and lowering
    happen once when this hook is constructed. Prefer
    :class:`dogwood.integrations.strands.DogwoodIntervention` for new
    integrations that need typed Strands decisions.
    """
    return _build_policy_hook(
        policy_source,
        policy_schema_source,
        event_schema_source=event_schema_source,
        action=action,
        principal=principal,
        resource=resource,
        input_mapper=input_mapper,
        mode=mode,
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


def lifecycle_hook(
    policy_source: str,
    policy_schema_source: str,
    *,
    event_schema_source: str | None = None,
    action: str | ActionResolver = "Agent::Action::CallTool",
    principal: str | IdentityResolver = default_principal,
    resource: str | IdentityResolver = default_resource,
    tool_input_mapper: InputMapper = default_tool_input,
    lifecycle_input_mapper: InputMapper = default_lifecycle_input,
    lifecycle_events: tuple[str, ...] | str = DEFAULT_LIFECYCLE_EVENTS,
    mode: EnforcementMode = "enforce",
    deny_message: str = "Dogwood policy denied this lifecycle event.",
) -> StrandsLifecyclePolicyHook:
    """Create a lifecycle-aware Strands hook backed by Dogwood.

    Pass ``lifecycle_events="all"`` to evaluate every supported lifecycle
    event, or pass a tuple such as ``("before_invocation", "before_tool_call",
    "after_tool_call")``.
    """
    authorizer = native.NativeAuthorizer(
        policy_source,
        policy_schema_source,
        event_schema_source,
    )
    return StrandsLifecyclePolicyHook(
        authorizer=authorizer,
        action=action,
        principal=principal,
        resource=resource,
        tool_input_mapper=tool_input_mapper,
        lifecycle_input_mapper=lifecycle_input_mapper,
        lifecycle_events=lifecycle_events,
        mode=mode,
        deny_message=deny_message,
    )


def _build_policy_hook(
    policy_source: str | None,
    policy_schema_source: str | None,
    *,
    event_schema_source: str | None = None,
    authorizer: native.NativeAuthorizer | None = None,
    action: str | ActionResolver,
    principal: str | IdentityResolver,
    resource: str | IdentityResolver,
    input_mapper: InputMapper,
    deny_message: str,
    mode: EnforcementMode = "enforce",
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
        mode=mode,
        deny_message=deny_message,
    )


__all__ = [
    "ALL_LIFECYCLE_EVENTS",
    "DEFAULT_LIFECYCLE_EVENTS",
    "StrandsLifecyclePolicyHook",
    "StrandsPolicyHook",
    "attach_before_tool_call_hook",
    "before_tool_call_hook",
    "lifecycle_hook",
]
