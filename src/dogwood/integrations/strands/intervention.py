from __future__ import annotations

from collections.abc import Callable, Iterable
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
from dogwood.integrations.strands.hooks import _build_policy_hook

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
PrecheckResolver = Callable[[Any], Any | None]


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
    """Typed Strands intervention handler backed by Dogwood authorization.

    ``before_tool_call`` returns Strands typed decisions when Strands is
    installed. Without Strands installed, it returns small local stand-ins so
    the mapping behavior remains testable.
    """

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
        confirm_when: ConfirmResolver = False,
        confirm_prompt: str = "Approve this Dogwood-controlled tool call?",
        precheck: PrecheckResolver | Iterable[PrecheckResolver] | None = None,
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
        self.confirm_when = confirm_when
        self.confirm_prompt = confirm_prompt
        self.prechecks = _precheck_list(precheck)

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        """Authorize a Strands tool call and return a typed control decision."""
        for precheck in self.prechecks:
            precheck_decision = _precheck_decision(precheck, event, self.policy_hook.deny_message)
            if precheck_decision is not None:
                return precheck_decision

        if _is_allowed(_authorize_event(self.policy_hook, event)):
            return _proceed()
        confirm_prompt = _confirm_prompt(self.confirm_when, self.confirm_prompt, event)
        if confirm_prompt is not None:
            return _confirm(confirm_prompt)
        return _deny(self.policy_hook.deny_message)


def _proceed() -> Any:
    if _StrandsProceed is not None:
        return _StrandsProceed()
    return _FallbackProceed()


def proceed() -> Any:
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
    return _transform(apply)


def _precheck_list(
    precheck: PrecheckResolver | Iterable[PrecheckResolver] | None,
) -> tuple[PrecheckResolver, ...]:
    if precheck is None:
        return ()
    if callable(precheck):
        return (precheck,)
    return tuple(precheck)


def _precheck_decision(
    precheck: PrecheckResolver,
    event: Any,
    default_deny_message: str,
) -> Any | None:
    result = precheck(event)
    if result is None or result is True:
        return None
    if result is False:
        return _deny(default_deny_message)
    if isinstance(result, str):
        return _deny(result)
    return result


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
