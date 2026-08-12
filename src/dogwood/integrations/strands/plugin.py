from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dogwood import native
from dogwood.integrations.strands.common import (
    ActionResolver,
    IdentityResolver,
    InputMapper,
    default_lifecycle_input,
    default_principal,
    default_resource,
    default_tool_input,
)
from dogwood.integrations.strands.hooks import (
    DEFAULT_LIFECYCLE_EVENTS,
    StrandsLifecyclePolicyHook,
    _build_policy_hook,
)

try:  # pragma: no cover - exercised only when the optional dependency exists
    try:
        from strands.hooks import AfterInvocationEvent as _AfterInvocationEvent
        from strands.hooks import AfterModelCallEvent as _AfterModelCallEvent
        from strands.hooks import AfterToolCallEvent as _AfterToolCallEvent
        from strands.hooks import BeforeInvocationEvent as _BeforeInvocationEvent
        from strands.hooks import BeforeModelCallEvent as _BeforeModelCallEvent
        from strands.hooks import BeforeToolCallEvent as _BeforeToolCallEvent
        from strands.hooks import MessageAddedEvent as _MessageAddedEvent
    except ImportError:
        from strands.hooks.events import AfterInvocationEvent as _AfterInvocationEvent
        from strands.hooks.events import AfterModelCallEvent as _AfterModelCallEvent
        from strands.hooks.events import AfterToolCallEvent as _AfterToolCallEvent
        from strands.hooks.events import BeforeInvocationEvent as _BeforeInvocationEvent
        from strands.hooks.events import BeforeModelCallEvent as _BeforeModelCallEvent
        from strands.hooks.events import BeforeToolCallEvent as _BeforeToolCallEvent
        from strands.hooks.events import MessageAddedEvent as _MessageAddedEvent
    from strands.plugins import Plugin as _StrandsPlugin
    from strands.plugins import hook as _strands_hook
except ImportError:  # pragma: no cover - keeps this module importable without Strands
    _AfterInvocationEvent = Any
    _AfterModelCallEvent = Any
    _AfterToolCallEvent = Any
    _BeforeInvocationEvent = Any
    _BeforeModelCallEvent = Any
    _BeforeToolCallEvent = Any
    _MessageAddedEvent = Any
    _StrandsPlugin = object

    def _strands_hook(func: Callable[..., Any]) -> Callable[..., Any]:
        return func


class DogwoodPlugin(_StrandsPlugin):
    """Strands plugin for lifecycle-wide Dogwood policy enforcement.

    ``DogwoodPlugin`` follows the Strands plugin pattern: it subclasses
    ``strands.plugins.Plugin`` and marks lifecycle methods with ``@hook`` so
    Strands can discover and register them automatically.

    Before-events can be cancelled when Dogwood denies. After-events are
    observed by Dogwood and continue. Use :class:`DogwoodIntervention` when you
    want Strands' typed ``Proceed`` / ``Deny`` / ``Confirm`` / ``Guide`` /
    ``Transform`` control flow instead.

    Constructor inputs mirror :class:`DogwoodIntervention`, except plugins use
    hook mutation semantics and do not return typed intervention actions.
    """

    name = "dogwood-policy"

    def __init__(
        self,
        policy_source: str | None = None,
        policy_schema_source: str | None = None,
        *,
        event_schema_source: str | None = None,
        authorizer: native.NativeAuthorizer | None = None,
        action: str | ActionResolver = "Agent::Action::CallTool",
        principal: str | IdentityResolver = default_principal,
        resource: str | IdentityResolver = default_resource,
        input_mapper: InputMapper = default_tool_input,
        lifecycle_input_mapper: InputMapper = default_lifecycle_input,
        lifecycle_events: tuple[str, ...] | str = DEFAULT_LIFECYCLE_EVENTS,
        deny_message: str = "Dogwood policy denied this tool call.",
    ) -> None:
        super().__init__()
        self.policy_hook = _build_policy_hook(
            policy_source,
            policy_schema_source,
            event_schema_source=event_schema_source,
            authorizer=authorizer,
            action=action,
            principal=principal,
            resource=resource,
            input_mapper=input_mapper,
            deny_message=deny_message,
        )
        self.lifecycle_hook = StrandsLifecyclePolicyHook(
            authorizer=self.policy_hook.authorizer,
            action=action,
            principal=principal,
            resource=resource,
            tool_input_mapper=input_mapper,
            lifecycle_input_mapper=lifecycle_input_mapper,
            lifecycle_events=lifecycle_events,
            deny_message=deny_message,
        )

    def init_agent(self, agent: Any) -> None:
        """Store the Strands agent instance during plugin initialization."""
        self.agent = agent

    @_strands_hook
    def on_before_invocation(self, event: _BeforeInvocationEvent) -> None:
        """Authorize the start of an agent invocation."""
        self.lifecycle_hook.handle("before_invocation", event)

    @_strands_hook
    def on_after_invocation(self, event: _AfterInvocationEvent) -> None:
        """Observe the end of an agent invocation."""
        self.lifecycle_hook.handle("after_invocation", event)

    @_strands_hook
    def on_message_added(self, event: _MessageAddedEvent) -> None:
        """Observe messages added to Strands conversation history."""
        self.lifecycle_hook.handle("message_added", event)

    @_strands_hook
    def on_before_model_call(self, event: _BeforeModelCallEvent) -> None:
        """Authorize a model call before Strands sends it."""
        self.lifecycle_hook.handle("before_model_call", event)

    @_strands_hook
    def on_after_model_call(self, event: _AfterModelCallEvent) -> None:
        """Observe a model response after Strands receives it."""
        self.lifecycle_hook.handle("after_model_call", event)

    @_strands_hook
    def on_before_tool_call(self, event: _BeforeToolCallEvent) -> None:
        """Authorize a ``BeforeToolCallEvent`` before Strands executes a tool."""
        self.lifecycle_hook.handle("before_tool_call", event)

    @_strands_hook
    def on_after_tool_call(self, event: _AfterToolCallEvent) -> None:
        """Observe a completed tool call."""
        self.lifecycle_hook.handle("after_tool_call", event)


__all__ = ["DogwoodPlugin"]
