from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

Value = Any


class Decision(str, Enum):
    ALLOW = "Allow"
    DENY = "Deny"


@dataclass(frozen=True)
class Entity:
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
    rule_index: int
    cedar_policy_id: str


@dataclass(frozen=True)
class Diagnostics:
    reason: tuple[DogwoodRuleRef, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Response:
    decision: Decision
    diagnostics: Diagnostics = field(default_factory=Diagnostics)

    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


@dataclass
class Event:
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
        return EventBuilder(action, kind)

    @property
    def action(self) -> str:
        return self.action_name

    @property
    def kind(self) -> str:
        return self.kind_name

    def timestamp(self) -> int:
        return self.ts

    def principal(self) -> str | None:
        return str(self.scope_principal) if self.scope_principal else None

    def resource(self) -> str | None:
        return str(self.scope_resource) if self.scope_resource else None

    def field(self, group: str, name: str) -> Value | None:
        value = self.logged.get(group)
        return value.get(name) if isinstance(value, dict) else None

    def fields(self, group: str) -> Iterable[tuple[str, Value]]:
        value = self.logged.get(group)
        return value.items() if isinstance(value, dict) else ()

    def field_path(self, path: list[str] | tuple[str, ...]) -> Value | None:
        return _descend(self.logged, path)

    def request_context_path(self, path: list[str] | tuple[str, ...]) -> Value | None:
        return _descend(self.request_ctx, path)


class EventBuilder:
    def __init__(self, action: str, kind: str):
        self._event = Event(_normalize_action(action), kind)

    def timestamp(self, ts: int) -> "EventBuilder":
        self._event.ts = int(ts)
        return self

    def principal(self, uid: str) -> "EventBuilder":
        self._event.scope_principal = Entity.parse(uid)
        return self

    def resource(self, uid: str) -> "EventBuilder":
        self._event.scope_resource = Entity.parse(uid)
        return self

    def field(self, group: str, name: str, value: Value) -> "EventBuilder":
        bucket = self._event.logged.setdefault(group, {})
        if not isinstance(bucket, dict):
            raise ValueError(f"logged field group {group!r} is not an object")
        bucket[name] = value
        return self

    def logged_group(self, group: str, value: dict[str, Value]) -> "EventBuilder":
        self._event.logged[group] = value
        return self

    def request_context(self, group: str, name: str, value: Value) -> "EventBuilder":
        bucket = self._event.request_ctx.setdefault(group, {})
        if not isinstance(bucket, dict):
            raise ValueError(f"request context group {group!r} is not an object")
        bucket[name] = value
        return self

    def request_context_group(self, group: str, value: dict[str, Value]) -> "EventBuilder":
        self._event.request_ctx[group] = value
        return self

    def build(self) -> Event:
        return self._event


class Authorizer:
    def __init__(self, policies: Any):
        self.policies = policies
        self.history: list[Event] = []

    def is_authorized(self, event: Event) -> Response | None:
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
