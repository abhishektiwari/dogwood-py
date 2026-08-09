"""Python value, event, response, and fallback authorizer types.

These classes mirror the names in ``dogwood_language`` so code written against
dogwood-py follows the Rust API shape. Schema-backed production behavior should
use :mod:`dogwood.native`; the classes here also power the temporary
schema-less fallback path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

Value = Any


class Decision(str, Enum):
    """Authorization decision.

    Rust mapping: ``dogwood_language::Decision``.
    """

    ALLOW = "Allow"
    DENY = "Deny"


@dataclass(frozen=True)
class Entity:
    """Cedar entity uid wrapper.

    Rust mapping: Dogwood events ultimately carry Cedar entity UIDs for
    principal/resource scope.
    """

    ty: str
    id: str

    @classmethod
    def parse(cls, text: str) -> "Entity":
        ty, raw_id = text.rsplit("::", 1)
        return cls(ty=ty, id=raw_id.strip('"'))

    def __str__(self) -> str:
        return f'{self.ty}::"{self.id}"'


@dataclass(frozen=True)
class DogwoodRuleRef:
    """Reference to an originating Dogwood rule.

    Rust mapping: ``dogwood_language::DogwoodRuleRef``.
    """

    rule_index: int
    cedar_policy_id: str


@dataclass(frozen=True)
class Diagnostics:
    """Decision diagnostics.

    Rust mapping: ``dogwood_language::Diagnostics``. Native diagnostics are not
    fully exposed through PyO3 yet; the fallback stores determining rule refs
    and errors.
    """

    reason: tuple[DogwoodRuleRef, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Response:
    """Authorization response.

    Rust mapping: ``dogwood_language::Response`` returned by
    ``Authorizer::is_authorized`` for decision-kind events.
    """

    decision: Decision
    diagnostics: Diagnostics = field(default_factory=Diagnostics)

    def allowed(self) -> bool:
        """Return true when ``decision`` is ``Decision.ALLOW``."""
        return self.decision is Decision.ALLOW


@dataclass
class Event:
    """Dogwood event.

    Rust mapping: ``dogwood_language::Event``. An event generalizes a Cedar
    request with a first-class ``kind`` such as ``request`` or ``response``.
    Decision kinds are defined by the Dogwood event schema; the default schema
    makes ``request`` a decision kind and ``response`` history-only.
    """

    action_name: str
    kind_name: str
    ts: int = 0
    scope_principal: Entity | None = None
    scope_resource: Entity | None = None
    logged: dict[str, Value] = field(default_factory=dict)
    request_ctx: dict[str, Value] = field(default_factory=dict)
    entities: dict[str, dict[str, Value]] = field(default_factory=dict)

    @classmethod
    def builder(cls, action: str, kind: str) -> "EventBuilder":
        """Start building an event.

        Rust mapping: ``Event::builder(action, kind)``.
        """
        return EventBuilder(action, kind)

    @property
    def action(self) -> str:
        return self.action_name

    @property
    def kind(self) -> str:
        return self.kind_name

    def timestamp(self) -> int:
        """Return the event timestamp.

        Rust mapping: ``Event::timestamp()``.
        """
        return self.ts

    def principal(self) -> str | None:
        """Return the request principal, if this event carries request scope.

        Rust mapping: ``Event::principal()``.
        """
        return str(self.scope_principal) if self.scope_principal else None

    def resource(self) -> str | None:
        """Return the request resource, if this event carries request scope.

        Rust mapping: ``Event::resource()``.
        """
        return str(self.scope_resource) if self.scope_resource else None

    def field(self, group: str, name: str) -> Value | None:
        """Read one logged event field.

        Rust mapping: ``Event::field(group, name)``.
        """
        value = self.logged.get(group)
        return value.get(name) if isinstance(value, dict) else None

    def fields(self, group: str) -> Iterable[tuple[str, Value]]:
        """Iterate logged event fields in a group.

        Rust mapping: ``Event::fields(group)``.
        """
        value = self.logged.get(group)
        return value.items() if isinstance(value, dict) else ()

    def field_path(self, path: list[str] | tuple[str, ...]) -> Value | None:
        return _descend(self.logged, path)

    def request_context_path(self, path: list[str] | tuple[str, ...]) -> Value | None:
        """Read a value from the Cedar request context path."""
        return _descend(self.request_ctx, path)


class EventBuilder:
    """Builder for :class:`Event`.

    Rust mapping: ``dogwood_language::EventBuilder``.
    """

    def __init__(self, action: str, kind: str):
        self._event = Event(_normalize_action(action), kind)

    def timestamp(self, ts: int) -> "EventBuilder":
        """Set the event timestamp.

        Rust mapping: ``EventBuilder::timestamp``.
        """
        self._event.ts = int(ts)
        return self

    def principal(self, uid: str) -> "EventBuilder":
        """Set request principal scope.

        Rust mapping: ``EventBuilder::principal``.
        """
        self._event.scope_principal = Entity.parse(uid)
        return self

    def resource(self, uid: str) -> "EventBuilder":
        """Set request resource scope.

        Rust mapping: ``EventBuilder::resource``.
        """
        self._event.scope_resource = Entity.parse(uid)
        return self

    def field(self, group: str, name: str, value: Value) -> "EventBuilder":
        """Add one logged event field.

        Rust mapping: ``EventBuilder::field``.
        """
        bucket = self._event.logged.setdefault(group, {})
        if not isinstance(bucket, dict):
            raise ValueError(f"logged field group {group!r} is not an object")
        bucket[name] = value
        return self

    def logged_group(self, group: str, value: dict[str, Value]) -> "EventBuilder":
        """Add a full logged event field group."""
        self._event.logged[group] = value
        return self

    def request_context(self, group: str, name: str, value: Value) -> "EventBuilder":
        """Add one Cedar request context field."""
        bucket = self._event.request_ctx.setdefault(group, {})
        if not isinstance(bucket, dict):
            raise ValueError(f"request context group {group!r} is not an object")
        bucket[name] = value
        return self

    def request_context_group(self, group: str, value: dict[str, Value]) -> "EventBuilder":
        """Add a full Cedar request context group."""
        self._event.request_ctx[group] = value
        return self

    def build(self) -> Event:
        """Return the constructed event.

        Rust mapping: ``EventBuilder::build``.
        """
        return self._event


class Authorizer:
    """Stateful fallback authorizer.

    Rust mapping: ``dogwood_language::Authorizer``. The native equivalent is
    :class:`dogwood.native.NativeAuthorizer`; this class is the temporary
    schema-less Python fallback.
    """

    def __init__(self, policies: Any):
        self.policies = policies
        self.history: list[Event] = []

    def is_authorized(self, event: Event) -> Response | None:
        """Authorize one event and record it in history.

        Rust mapping: ``Authorizer::is_authorized(&event) -> Option<Response>``.
        Returns ``None`` for history-only events. In the fallback, only
        ``request`` is treated as a decision kind.
        """
        self.history.append(event)
        if event.kind != "request":
            return None
        return self.policies.decide(event, self.history[:-1])


def _descend(value: Any, path: list[str] | tuple[str, ...]) -> Any | None:
    cur = value
    for segment in path:
        if not isinstance(cur, dict) or segment not in cur:
            return None
        cur = cur[segment]
    return cur


def _normalize_action(action: str) -> str:
    return action.replace('::"', "::").replace('"', "")
