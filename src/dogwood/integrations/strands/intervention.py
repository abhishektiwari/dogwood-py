from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dogwood import native
from dogwood.integrations.strands.common import (
    IdentityResolver,
    InputMapper,
    _authorize_event,
    _event_enabled,
    _is_allowed,
    default_lifecycle_input,
    default_principal,
    default_resource,
    default_tool_input,
)
from dogwood.integrations.strands.hooks import DEFAULT_LIFECYCLE_EVENTS, _build_policy_hook

try:  # pragma: no cover - exercised only when the optional dependency exists
    from strands.interventions import (
        Confirm as _StrandsConfirm,
        Deny as _StrandsDeny,
        Guide as _StrandsGuide,
        InterventionHandler as _StrandsInterventionHandler,
        Proceed as _StrandsProceed,
        Transform as _StrandsTransform,
    )
except ImportError:  # pragma: no cover - fallback is covered through behavior tests
    _StrandsConfirm = None
    _StrandsDeny = None
    _StrandsGuide = None
    _StrandsInterventionHandler = object
    _StrandsProceed = None
    _StrandsTransform = None

ConfirmResolver = bool | str | Callable[[Any], bool | str | None]


@dataclass(frozen=True)
class _FallbackProceed:
    """Local stand-in used when Strands is not installed."""


@dataclass(frozen=True)
class _FallbackDeny:
    """Local stand-in used when Strands is not installed."""

    reason: str


@dataclass(frozen=True)
class _FallbackConfirm:
    """Local stand-in used when Strands is not installed."""

    prompt: str


@dataclass(frozen=True)
class _FallbackGuide:
    """Local stand-in used when Strands is not installed."""

    feedback: str


@dataclass(frozen=True)
class _FallbackTransform:
    """Local stand-in used when Strands is not installed."""

    apply: Callable[[Any], Any]


class DogwoodIntervention(_StrandsInterventionHandler):
    """Strands intervention handler backed by Dogwood authorization.

    Interventions are the preferred integration point for agent control flows
    because they return typed Strands decisions instead of mutating hook events
    directly. ``DogwoodIntervention`` can evaluate Dogwood policies across the
    primary Strands lifecycle methods:

    * ``before_invocation``
    * ``before_model_call``
    * ``before_tool_call``
    * ``after_tool_call``
    * ``after_model_call``

    For ``before_tool_call`` it returns:

    * ``Proceed`` when Dogwood allows the tool call.
    * ``Deny`` when Dogwood denies the tool call.
    * ``Confirm`` when Dogwood denies and ``confirm_when`` requests human
      approval.

    Without Strands installed, the class returns small local stand-ins so the
    mapping behavior remains testable.

    Constructor inputs:

    * ``policy_source`` and ``policy_schema_source`` build a persistent native
      Dogwood authorizer.
    * ``event_schema_source`` supplies an explicit Dogwood ``.dwschema``.
    * ``authorizer`` reuses an existing :class:`dogwood.native.NativeAuthorizer`
      instead of building one.
    * ``principal``, ``resource``, and ``input_mapper`` customize how Strands
      events are mapped into Dogwood authorization requests.
    * ``confirm_when`` turns Dogwood denials into Strands ``Confirm`` actions
      for selected tool calls.
    * ``lifecycle_events`` selects which lifecycle methods invoke Dogwood.
      The default is ``("before_tool_call",)`` for backward compatibility.
      Use ``"all"`` to evaluate every supported intervention lifecycle.
    """

    name = "dogwood-policy"

    def __init__(
        self,
        policy_source: str | None = None,
        policy_schema_source: str | None = None,
        *,
        event_schema_source: str | None = None,
        authorizer: native.NativeAuthorizer | None = None,
        action: str = "Drupe::Action::CallTool",
        principal: str | IdentityResolver = default_principal,
        resource: str | IdentityResolver = default_resource,
        input_mapper: InputMapper = default_tool_input,
        lifecycle_input_mapper: InputMapper = default_lifecycle_input,
        lifecycle_events: tuple[str, ...] | str = DEFAULT_LIFECYCLE_EVENTS,
        deny_message: str = "Dogwood policy denied this tool call.",
        confirm_when: ConfirmResolver = False,
        confirm_prompt: str = "Approve this Dogwood-controlled tool call?",
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
        self.lifecycle_input_mapper = lifecycle_input_mapper
        self.lifecycle_events = lifecycle_events
        self.confirm_when = confirm_when
        self.confirm_prompt = confirm_prompt

    def before_invocation(self, event: Any, **kwargs: Any) -> Any:
        """Authorize the start of an agent invocation."""
        return self._before_lifecycle("before_invocation", event)

    def before_model_call(self, event: Any, **kwargs: Any) -> Any:
        """Authorize a model call before the request is sent."""
        return self._before_lifecycle("before_model_call", event)

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        """Authorize a Strands tool call and return a typed control decision.

        This method is called by Strands for ``BeforeToolCallEvent``. Dogwood
        receives the selected tool name, tool input, and tool-use identifier via
        the configured ``input_mapper``.
        """
        decision = self._authorize_lifecycle("before_tool_call", event)
        if decision is None or _is_allowed(decision):
            return _proceed()
        confirm_prompt = _confirm_prompt(self.confirm_when, self.confirm_prompt, event)
        if confirm_prompt is not None:
            return _confirm(confirm_prompt)
        return _deny(self.policy_hook.deny_message)

    def after_tool_call(self, event: Any, **kwargs: Any) -> Any:
        """Observe a completed tool call and continue.

        Strands after-tool-call interventions support ``Proceed`` and
        ``Transform``. Dogwood denials are therefore observational here; hard
        enforcement belongs in ``before_tool_call``.
        """
        self._authorize_lifecycle("after_tool_call", event)
        return _proceed()

    def after_model_call(self, event: Any, **kwargs: Any) -> Any:
        """Observe a model response and optionally guide on Dogwood denial."""
        decision = self._authorize_lifecycle("after_model_call", event)
        if decision is not None and not _is_allowed(decision):
            return _guide(self.policy_hook.deny_message)
        return _proceed()

    def _before_lifecycle(self, lifecycle: str, event: Any) -> Any:
        decision = self._authorize_lifecycle(lifecycle, event)
        if decision is not None and not _is_allowed(decision):
            return _deny(self.policy_hook.deny_message)
        return _proceed()

    def _authorize_lifecycle(self, lifecycle: str, event: Any) -> Any | None:
        setattr(event, "dogwood_lifecycle", lifecycle)
        if not _event_enabled(self.lifecycle_events, lifecycle):
            return None
        if lifecycle == "before_tool_call":
            return _authorize_event(self.policy_hook, event)
        return _authorize_event(_LifecyclePolicyView(self, self.lifecycle_input_mapper), event)


@dataclass(frozen=True)
class _LifecyclePolicyView:
    intervention: DogwoodIntervention
    input_mapper: InputMapper

    @property
    def authorizer(self) -> Any:
        return self.intervention.policy_hook.authorizer

    @property
    def action(self) -> str:
        return self.intervention.policy_hook.action

    @property
    def principal(self) -> Any:
        return self.intervention.policy_hook.principal

    @property
    def resource(self) -> Any:
        return self.intervention.policy_hook.resource


def _proceed() -> Any:
    if _StrandsProceed is not None:
        return _StrandsProceed()
    return _FallbackProceed()


def proceed() -> Any:
    """Return a Strands ``Proceed`` action, or a local stand-in for tests."""
    return _proceed()


def _deny(message: str) -> Any:
    if _StrandsDeny is None:
        return _FallbackDeny(message)

    for kwargs in ({"reason": message}, {"message": message}):
        try:
            return _StrandsDeny(**kwargs)
        except TypeError:
            pass

    try:
        return _StrandsDeny(message)
    except TypeError:
        return _StrandsDeny()


def deny(message: str) -> Any:
    """Return a Strands ``Deny`` action with a denial reason."""
    return _deny(message)


def _confirm(prompt: str) -> Any:
    if _StrandsConfirm is None:
        return _FallbackConfirm(prompt)

    for kwargs in ({"prompt": prompt}, {"message": prompt}, {"reason": prompt}):
        try:
            return _StrandsConfirm(**kwargs)
        except TypeError:
            pass

    try:
        return _StrandsConfirm(prompt)
    except TypeError:
        return _StrandsConfirm()


def confirm(prompt: str) -> Any:
    """Return a Strands ``Confirm`` action with a human approval prompt."""
    return _confirm(prompt)


def _guide(feedback: str) -> Any:
    if _StrandsGuide is None:
        return _FallbackGuide(feedback)

    for kwargs in ({"feedback": feedback}, {"message": feedback}, {"reason": feedback}):
        try:
            return _StrandsGuide(**kwargs)
        except TypeError:
            pass

    try:
        return _StrandsGuide(feedback)
    except TypeError:
        return _StrandsGuide()


def guide(feedback: str) -> Any:
    """Return a Strands ``Guide`` action with corrective model feedback."""
    return _guide(feedback)


def _transform(apply: Callable[[Any], Any]) -> Any:
    if _StrandsTransform is None:
        return _FallbackTransform(apply)

    for kwargs in ({"apply": apply}, {"transform": apply}, {"fn": apply}):
        try:
            return _StrandsTransform(**kwargs)
        except TypeError:
            pass

    try:
        return _StrandsTransform(apply)
    except TypeError:
        return _StrandsTransform()


def transform(apply: Callable[[Any], Any]) -> Any:
    """Return a Strands ``Transform`` action that mutates an event in place."""
    return _transform(apply)


def _confirm_prompt(
    confirm_when: ConfirmResolver,
    default_prompt: str,
    event: Any,
) -> str | None:
    if confirm_when is False:
        return None
    if confirm_when is True:
        return default_prompt
    if isinstance(confirm_when, str):
        return confirm_when
    result = confirm_when(event)
    if result is False or result is None:
        return None
    if result is True:
        return default_prompt
    return str(result)


__all__ = [
    "DogwoodIntervention",
    "confirm",
    "deny",
    "guide",
    "proceed",
    "transform",
]
