from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dogwood import native
from dogwood.integrations.strands.common import (
    IdentityResolver,
    InputMapper,
    default_principal,
    default_resource,
    default_tool_input,
)
from dogwood.integrations.strands.hooks import _build_policy_hook

try:  # pragma: no cover - exercised only when the optional dependency exists
    from strands.plugins import Plugin as _StrandsPlugin
    from strands.plugins import hook as _strands_hook
except ImportError:  # pragma: no cover - keeps this module importable without Strands
    _StrandsPlugin = object

    def _strands_hook(func: Callable[..., Any]) -> Callable[..., Any]:
        return func


class DogwoodPlugin(_StrandsPlugin):
    """Strands plugin that auto-registers Dogwood's before-tool-call hook."""

    name = "dogwood-policy"

    def __init__(
        self,
        policy_source: str | None = None,
        policy_schema_source: str | None = None,
        *,
        authorizer: native.NativeAuthorizer | None = None,
        action: str = "Drupe::Action::CallTool",
        principal: str | IdentityResolver = default_principal,
        resource: str | IdentityResolver = default_resource,
        input_mapper: InputMapper = default_tool_input,
        deny_message: str = "Dogwood policy denied this tool call.",
    ) -> None:
        super().__init__()
        self.policy_hook = _build_policy_hook(
            policy_source,
            policy_schema_source,
            authorizer=authorizer,
            action=action,
            principal=principal,
            resource=resource,
            input_mapper=input_mapper,
            deny_message=deny_message,
        )

    def init_agent(self, agent: Any) -> None:
        self.agent = agent

    @_strands_hook
    def on_before_tool_call(self, event: Any) -> None:
        self.policy_hook(event)


__all__ = ["DogwoodPlugin"]
