from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .errors import ParseError
from . import native
from .values import Decision, Diagnostics, DogwoodRuleRef, Response


@dataclass(frozen=True)
class ServiceSchema:
    event_schema: str | None = None
    macros: str | None = None
    providers: dict[str, Any] | None = None

    @classmethod
    def defaults(cls) -> "ServiceSchema":
        return cls()


@dataclass(frozen=True)
class PolicySchema:
    source: str

    @classmethod
    def from_cedarschema_str(cls, source: str) -> "PolicySchema":
        return cls(source)


@dataclass(frozen=True)
class ParsedPolicy:
    id: str
    effect: str
    action: str | None
    when: tuple[str, ...] = ()
    unless: tuple[str, ...] = ()
    temporal: tuple[str, ...] = ()
    index: int = 0

    def uses_temporal(self) -> bool:
        return bool(self.temporal)

    def uses_providers(self) -> bool:
        return False


@dataclass(frozen=True)
class ParsedPolicySet:
    source: str
    service_schema: ServiceSchema
    _policies: tuple[ParsedPolicy, ...]

    @classmethod
    def parse(cls, source: str, service_schema: ServiceSchema | None = None) -> "ParsedPolicySet":
        service_schema = service_schema or ServiceSchema.defaults()
        return cls(source, service_schema, tuple(_parse_policies(source)))

    def lower(self, policy_schema: PolicySchema) -> "LoweredPolicySet":
        return LoweredPolicySet(self, policy_schema)

    def lower_with_distincter(self, policy_schema: PolicySchema, distincter: str) -> "LoweredPolicySet":
        if not re.match(r"^[_A-Za-z][_A-Za-z0-9]*$", distincter):
            raise ParseError(f"invalid distincter {distincter!r}")
        return LoweredPolicySet(self, policy_schema, distincter=distincter)

    def policy_count(self) -> int:
        return len(self._policies)

    def policies(self) -> tuple[ParsedPolicy, ...]:
        return self._policies


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def validation_passed(self) -> bool:
        return not self.errors


class Validator:
    def validate(self, policies: "LoweredPolicySet") -> ValidationResult:
        if policies.policy_schema.source.strip():
            native.require_available()
            result = native.validate_policy(policies.source, policies.policy_schema.source)
            return ValidationResult(tuple(result["errors"]), tuple(result["warnings"]))
        errors: list[str] = []
        if not policies.parsed._policies:
            errors.append("policy set is empty")
        for policy in policies.parsed._policies:
            if policy.effect not in {"permit", "forbid"}:
                errors.append(f"policy {policy.id}: unsupported effect {policy.effect}")
        return ValidationResult(tuple(errors))


@dataclass
class LoweredPolicySet:
    parsed: ParsedPolicySet
    policy_schema: PolicySchema
    distincter: str = "policy"
    cedar_policies: str = field(init=False)
    source: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", self.parsed.source)
        cedar = self._render_cedar()
        if self.policy_schema.source.strip():
            native.require_available()
            cedar = native.lower_to_cedar(self.parsed.source, self.policy_schema.source)
        object.__setattr__(self, "cedar_policies", cedar)

    @classmethod
    def from_str(
        cls,
        source: str,
        service_schema: ServiceSchema | None = None,
        policy_schema: PolicySchema | None = None,
    ) -> "LoweredPolicySet":
        parsed = ParsedPolicySet.parse(source, service_schema or ServiceSchema.defaults())
        return parsed.lower(policy_schema or PolicySchema(""))

    def as_cedar(self) -> str:
        return self.cedar_policies

    def cedar_schema(self) -> str:
        if self.policy_schema.source.strip():
            native.require_available()
            return native.cedar_schema(self.source, self.policy_schema.source)
        return self.policy_schema.source

    def is_self_contained_cedar(self) -> bool:
        return not any(policy.temporal for policy in self.parsed._policies)

    def decide(self, event: Any, history: list[Any]) -> Response:
        matched_forbid: list[DogwoodRuleRef] = []
        matched_permit: list[DogwoodRuleRef] = []
        errors: list[str] = []
        for policy in self.parsed._policies:
            try:
                if _policy_matches(policy, event, history):
                    ref = DogwoodRuleRef(policy.index, f"{self.distincter}{policy.index}")
                    if policy.effect == "forbid":
                        matched_forbid.append(ref)
                    else:
                        matched_permit.append(ref)
            except Exception as exc:
                errors.append(f"policy {policy.id}: {exc}")
        if errors or matched_forbid:
            return Response(Decision.DENY, Diagnostics(tuple(matched_forbid), tuple(errors)))
        if matched_permit:
            return Response(Decision.ALLOW, Diagnostics(tuple(matched_permit), ()))
        return Response(Decision.DENY, Diagnostics())

    def _render_cedar(self) -> str:
        lines = []
        for policy in self.parsed._policies:
            clauses = list(policy.when)
            clauses.extend(f"!({expr})" for expr in policy.unless)
            if policy.temporal:
                clauses.extend(f"context.{self.distincter}_{policy.index}__temporal_{i}" for i, _ in enumerate(policy.temporal))
            guard = " && ".join(clauses) if clauses else "true"
            action = f"action == {policy.action}" if policy.action else "action"
            lines.append(
                f'@id("{policy.id}")\n{policy.effect}(principal, {action}, resource) when {{ {guard} }};'
            )
        return "\n".join(lines)


def _parse_policies(source: str) -> list[ParsedPolicy]:
    clean = re.sub(r"//.*", "", source)
    chunks = [chunk.strip() for chunk in clean.split(";") if chunk.strip()]
    policies: list[ParsedPolicy] = []
    for index, chunk in enumerate(chunks):
        policy_id = f"policy{index}"
        id_match = re.search(r'@id\s*\(\s*"([^"]+)"\s*\)', chunk)
        if id_match:
            policy_id = id_match.group(1)
            chunk = chunk[: id_match.start()] + chunk[id_match.end() :]
        effect_match = re.search(r"\b(permit|forbid)\s*\((.*?)\)", chunk, re.S)
        if not effect_match:
            raise ParseError(f"could not parse policy {index}")
        effect = effect_match.group(1)
        scope = " ".join(effect_match.group(2).split())
        action_match = re.search(r"action\s*==\s*([^,\)]+)", scope)
        action = action_match.group(1).strip() if action_match else None
        tail = chunk[effect_match.end() :]
        when: list[str] = []
        unless: list[str] = []
        temporal: list[str] = []
        for kind, body in _extract_clauses(tail):
            if kind == "when temporal":
                temporal.append(body)
            elif kind == "when guardrail":
                when.append(body)
            elif kind == "when":
                when.append(body)
            elif kind == "unless":
                unless.append(body)
        policies.append(ParsedPolicy(policy_id, effect, action, tuple(when), tuple(unless), tuple(temporal), index))
    return policies


def _extract_clauses(text: str) -> list[tuple[str, str]]:
    clauses: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        match = re.search(r"\b(when\s+temporal|when\s+guardrail|when|unless)\s*\{", text[i:])
        if not match:
            break
        kind = " ".join(match.group(1).split())
        start = i + match.end()
        depth = 1
        j = start
        in_string = False
        while j < len(text):
            ch = text[j]
            if ch == '"' and (j == 0 or text[j - 1] != "\\"):
                in_string = not in_string
            elif not in_string and ch == "{":
                depth += 1
            elif not in_string and ch == "}":
                depth -= 1
                if depth == 0:
                    clauses.append((kind, text[start:j].strip()))
                    i = j + 1
                    break
            j += 1
        else:
            raise ParseError("unclosed policy clause")
    return clauses


def _policy_matches(policy: ParsedPolicy, event: Any, history: list[Any]) -> bool:
    if policy.action and _normalize_action(policy.action) != event.action:
        return False
    for expr in policy.when:
        if not _eval_expr(expr, event):
            return False
    for expr in policy.unless:
        if _eval_expr(expr, event):
            return False
    for expr in policy.temporal:
        if not _eval_temporal(expr, event, history):
            return False
    return True


def _eval_temporal(expr: str, event: Any, history: list[Any]) -> bool:
    match = re.search(
        r"formerly(?:\s+within\s+(\d+)([smhd]))?\s+(.+?)::([A-Za-z_]\w*)\s*(?:\{(.*)\})?\s*$",
        " ".join(expr.split()),
    )
    if not match:
        raise ValueError(f"unsupported temporal expression: {expr}")
    amount, unit, action, kind, pins = match.groups()
    window = None if amount is None else int(amount) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    wanted_action = _normalize_action(action)
    pin_pairs = _parse_pins(pins or "")
    for past in reversed(history):
        if past.action != wanted_action or past.kind != kind:
            continue
        if window is not None and event.timestamp() - past.timestamp() > window:
            continue
        if all(past.field_path(left.split(".")) == _resolve_ref(right, event) for left, right in pin_pairs):
            return True
    return False


def _parse_pins(text: str) -> list[tuple[str, str]]:
    if not text.strip():
        return []
    out = []
    for item in _split_top_level(text, ","):
        if ":" not in item:
            continue
        left, right = item.split(":", 1)
        out.append((left.strip(), right.strip()))
    return out


def _eval_expr(expr: str, event: Any) -> bool:
    expr = expr.strip()
    if not expr:
        return True
    or_parts = _split_operator(expr, "||")
    if len(or_parts) > 1:
        return any(_eval_expr(part, event) for part in or_parts)
    and_parts = _split_operator(expr, "&&")
    if len(and_parts) > 1:
        return all(_eval_expr(part, event) for part in and_parts)
    if expr.startswith("!"):
        return not _eval_expr(expr[1:].strip(), event)
    if expr.startswith("(") and expr.endswith(")"):
        return _eval_expr(expr[1:-1], event)
    for op in ("<=", ">=", "==", "!=", "<", ">"):
        parts = _split_operator(expr, op)
        if len(parts) == 2:
            left = _resolve_ref(parts[0].strip(), event)
            right = _literal(parts[1].strip(), event)
            return _compare(left, op, right)
    value = _literal(expr, event)
    return bool(value)


def _resolve_ref(text: str, event: Any) -> Any:
    text = text.strip()
    if text.startswith("context."):
        return event.request_context_path(text.removeprefix("context.").split("."))
    if text.startswith("principal."):
        entity = event.scope_principal
        return getattr(entity, text.removeprefix("principal."), None) if entity else None
    if text.startswith("resource."):
        entity = event.scope_resource
        return getattr(entity, text.removeprefix("resource."), None) if entity else None
    return _literal(text, event)


def _literal(text: str, event: Any) -> Any:
    text = text.strip()
    if text.startswith("context.") or text.startswith("principal.") or text.startswith("resource."):
        return _resolve_ref(text, event)
    if text == "true":
        return True
    if text == "false":
        return False
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if re.match(r"^-?\d+$", text):
        return int(text)
    if re.match(r"^-?\d+\.\d+$", text):
        return float(text)
    return _normalize_action(text)


def _compare(left: Any, op: str, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if left is None or right is None:
        return False
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    raise ValueError(op)


def _split_operator(expr: str, op: str) -> list[str]:
    return _split_top_level(expr, op)


def _split_top_level(expr: str, sep: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_string = False
    start = 0
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == '"' and (i == 0 or expr[i - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth -= 1
            elif depth == 0 and expr.startswith(sep, i):
                parts.append(expr[start:i].strip())
                i += len(sep)
                start = i
                continue
        i += 1
    parts.append(expr[start:].strip())
    return parts


def _normalize_action(action: str) -> str:
    return action.strip().replace('::"', "::").replace('"', "")
