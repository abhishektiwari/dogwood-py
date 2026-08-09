"""Trace parsing and replay helpers.

Rust mapping:

* :func:`parse_trace` mirrors ``dogwood_language::parse_trace`` for the subset
  needed by the Python fallback.
* :func:`replay_log` maps to ``dogwood_language::replay_log`` when a
  schema-backed ``LoweredPolicySet`` is supplied, otherwise it uses the
  temporary Python fallback ``Authorizer``.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import ParseError
from . import native
from .values import Entity, Event


def parse_trace(log: str) -> list[Event]:
    """Parse Dogwood trace log text into ``Event`` objects.

    Rust mapping: ``dogwood_language::parse_trace``.
    """
    events = []
    for line_no, raw in enumerate(log.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        try:
            events.append(_parse_line(line))
        except Exception as exc:
            raise ParseError(f"trace line {line_no}: {exc}") from exc
    return events


def replay_log(policies: Any, log: str) -> str:
    """Replay a trace against a policy set and return CLI-style verdict lines.

    Rust mapping: ``dogwood_language::replay_log`` for schema-backed native
    policy sets. The fallback path feeds parsed events into
    ``dogwood.values.Authorizer``.
    """
    if (
        hasattr(policies, "source")
        and hasattr(policies, "policy_schema")
        and policies.policy_schema.source.strip()
    ):
        native.require_available()
        return native.replay(
            policies.source,
            policies.policy_schema.source,
            log,
            policies.parsed.service_schema.event_schema,
        )

    from .values import Authorizer

    authorizer = Authorizer(policies)
    lines = []
    for i, event in enumerate(parse_trace(log)):
        response = authorizer.is_authorized(event)
        if response is not None:
            allowed = "true" if response.allowed() else "false"
            lines.append(f"@{event.timestamp()} (time point {i}): {allowed}")
    return "\n".join(lines)


def _parse_line(line: str) -> Event:
    ts_match = re.match(r"@(-?\d+)\s+", line)
    if not ts_match:
        raise ValueError("missing @timestamp")
    ts = int(ts_match.group(1))
    rest = line[ts_match.end() :].strip()
    scope = {}
    request_context = {}
    if rest.startswith("scope("):
        body, rest = _consume_call(rest, "scope")
        scope = _parse_pairs(body)
    if rest.startswith("request_context("):
        body, rest = _consume_call(rest, "request_context")
        request_context = _parse_pairs(body)
    event_match = re.match(r'(.+::"[^"]+"|[A-Za-z_][\w:]*)::([A-Za-z_]\w*)\((.*)\)\s*$', rest)
    if not event_match:
        raise ValueError("missing event action")
    action, kind, fields_src = event_match.groups()
    builder = Event.builder(action, kind).timestamp(ts)
    if "principal" in scope:
        builder.principal(str(scope["principal"]))
    if "resource" in scope:
        builder.resource(str(scope["resource"]))
    for group, value in request_context.items():
        if isinstance(value, dict):
            builder.request_context_group(group, value)
        else:
            builder.request_context_group(group, {"value": value})
    for group, value in _parse_pairs(fields_src).items():
        if isinstance(value, dict):
            builder.logged_group(group, value)
        else:
            builder.logged_group(group, {"value": value})
    return builder.build()


def _consume_call(text: str, name: str) -> tuple[str, str]:
    prefix = f"{name}("
    if not text.startswith(prefix):
        raise ValueError(f"expected {name}(...)")
    start = len(prefix)
    depth = 1
    in_string = False
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '"' and text[i - 1] != "\\":
            in_string = not in_string
        elif not in_string and ch == "(":
            depth += 1
        elif not in_string and ch == ")":
            depth -= 1
            if depth == 0:
                return text[start:i], text[i + 1 :].strip()
        i += 1
    raise ValueError(f"unclosed {name}(...)")


def _parse_pairs(text: str) -> dict[str, Any]:
    parser = _ValueParser("{" + text + "}")
    value = parser.parse_value()
    if not isinstance(value, dict):
        raise ValueError("expected field object")
    return value


class _ValueParser:
    def __init__(self, text: str):
        self.text = text
        self.i = 0

    def parse_value(self) -> Any:
        self._ws()
        ch = self._peek()
        if ch == "{":
            return self._object()
        if ch == "[":
            return self._array()
        if ch == '"':
            return self._string()
        token = self._token()
        if token == "true":
            return True
        if token == "false":
            return False
        if token == "null":
            return None
        if re.match(r"^-?\d+$", token):
            return int(token)
        if re.match(r"^-?\d+\.\d+$", token):
            return float(token)
        if "::" in token:
            return Entity.parse(token)
        return token

    def _object(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        self._expect("{")
        self._ws()
        while self._peek() != "}":
            key = self._key()
            self._ws()
            self._expect(":")
            out[key] = self.parse_value()
            self._ws()
            if self._peek() == ",":
                self.i += 1
                self._ws()
            else:
                break
        self._expect("}")
        return out

    def _array(self) -> list[Any]:
        out = []
        self._expect("[")
        self._ws()
        while self._peek() != "]":
            out.append(self.parse_value())
            self._ws()
            if self._peek() == ",":
                self.i += 1
                self._ws()
            else:
                break
        self._expect("]")
        return out

    def _key(self) -> str:
        self._ws()
        return self._string() if self._peek() == '"' else self._bare_key()

    def _string(self) -> str:
        self._expect('"')
        start = self.i
        escaped = False
        out = []
        while self.i < len(self.text):
            ch = self.text[self.i]
            self.i += 1
            if escaped:
                out.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                return "".join(out)
            else:
                out.append(ch)
        raise ValueError("unclosed string")

    def _token(self) -> str:
        self._ws()
        start = self.i
        in_quote = False
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch == '"':
                in_quote = not in_quote
            if not in_quote and (ch.isspace() or ch in ",{}[]"):
                break
            self.i += 1
        if self.i == start:
            raise ValueError(f"expected token near {self.text[self.i:self.i + 20]!r}")
        return self.text[start : self.i]

    def _bare_key(self) -> str:
        self._ws()
        start = self.i
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch.isspace() or ch in ":,{}[]":
                break
            self.i += 1
        if self.i == start:
            raise ValueError(f"expected key near {self.text[self.i:self.i + 20]!r}")
        return self.text[start : self.i]

    def _expect(self, ch: str) -> None:
        self._ws()
        if self._peek() != ch:
            raise ValueError(f"expected {ch!r}")
        self.i += 1

    def _peek(self) -> str:
        return self.text[self.i] if self.i < len(self.text) else ""

    def _ws(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1
