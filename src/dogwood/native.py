"""Native PyO3 wrappers around the Rust ``dogwood_language`` API.

The functions in this module are the closest Python surface to the reference
Rust implementation described in Dogwood's API and workflow guide.

Mapping to Rust:

* :class:`NativeAuthorizer` wraps
  ``dogwood_language::Authorizer::new(LoweredPolicySet)`` and feeds request
  events through ``Authorizer::is_authorized``.
* :func:`lower_to_cedar` maps to ``LoweredPolicySet::from_str(...).as_cedar()``.
* :func:`cedar_schema` maps to ``LoweredPolicySet::cedar_schema_str()``.
* :func:`validate_policy` maps to ``Validator::new().validate(&policies)``.
* :func:`replay` maps to ``dogwood_language::replay_log``.

All schema-backed operations require the maturin-built extension module
``dogwood._dogwood_native``.
"""

from __future__ import annotations

import json
from typing import Any

try:
    from . import _dogwood_native
except ImportError:  # pragma: no cover - exercised only before native build
    _dogwood_native = None


def available() -> bool:
    """Return whether the Rust ``dogwood_language`` extension is importable."""
    return _dogwood_native is not None and _dogwood_native.native_available()


def require_available() -> None:
    """Raise ``RuntimeError`` if the native Rust extension is unavailable."""
    if not available():
        raise RuntimeError(
            "dogwood native extension is required for schema-backed operations; "
            "run `make develop` or install the maturin-built wheel"
        )


class NativeAuthorizer:
    """Persistent native Dogwood authorizer.

    Rust mapping:

    * Builds ``ServiceSchema`` from ``event_schema_source`` or
      ``ServiceSchema::defaults()``.
    * Builds ``PolicySchema::from_cedarschema_str(policy_schema_source)``.
    * Lowers with ``LoweredPolicySet::from_str``.
    * Stores ``dogwood_language::Authorizer`` and calls
      ``Authorizer::is_authorized`` for each request.

    The object is stateful: every authorization call records the event in the
    underlying Rust authorizer history, so temporal policies can observe prior
    events.
    """

    def __init__(
        self,
        policy_source: str,
        policy_schema_source: str,
        event_schema_source: str | None = None,
    ):
        require_available()
        self._inner = _dogwood_native.NativeAuthorizer(
            policy_source,
            policy_schema_source,
            event_schema_source,
        )

    def authorize_request(
        self,
        action: str,
        principal: str,
        resource: str,
        input: dict[str, Any],
    ) -> str:
        """Authorize one request event and return ``"Allow"`` or ``"Deny"``.

        Rust mapping: builds a ``dogwood_language::Event`` with kind
        ``"request"`` from the supplied action, principal, resource, and input,
        then calls ``Authorizer::is_authorized``.
        """
        return self._inner.authorize_request(
            action,
            principal,
            resource,
            json.dumps(input),
        )


def lower_to_cedar(
    policy_source: str,
    policy_schema_source: str,
    event_schema_source: str | None = None,
) -> str:
    """Lower Dogwood policy source to Cedar policy text.

    Rust mapping: ``LoweredPolicySet::from_str`` followed by
    ``LoweredPolicySet::as_cedar`` rendering.
    """
    require_available()
    return _dogwood_native.lower_to_cedar(policy_source, policy_schema_source, event_schema_source)


def cedar_schema(
    policy_source: str,
    policy_schema_source: str,
    event_schema_source: str | None = None,
) -> str:
    """Return the augmented Cedar schema emitted by Dogwood lowering.

    Rust mapping: ``LoweredPolicySet::cedar_schema_str``.
    """
    require_available()
    return _dogwood_native.cedar_schema(policy_source, policy_schema_source, event_schema_source)


def validate_policy(
    policy_source: str,
    policy_schema_source: str,
    event_schema_source: str | None = None,
) -> dict[str, Any]:
    """Validate policy source against the supplied schemas.

    Rust mapping: ``LoweredPolicySet::from_str`` then
    ``Validator::new().validate(&policies)``.
    """
    require_available()
    return dict(_dogwood_native.validate_policy(policy_source, policy_schema_source, event_schema_source))


def replay(
    policy_source: str,
    policy_schema_source: str,
    trace_source: str,
    event_schema_source: str | None = None,
) -> str:
    """Replay a Dogwood trace and return CLI-style verdict lines.

    Rust mapping: ``dogwood_language::replay_log`` after lowering the policy
    set against the provided action and optional event schemas.
    """
    require_available()
    return _dogwood_native.replay(
        policy_source,
        policy_schema_source,
        trace_source,
        event_schema_source,
    )


def authorize_request(
    policy_source: str,
    policy_schema_source: str,
    action: str,
    principal: str,
    resource: str,
    input: dict[str, Any],
    event_schema_source: str | None = None,
) -> str:
    """One-shot native authorization.

    Rust mapping: lower policy source into a fresh ``LoweredPolicySet``, create
    a fresh ``Authorizer``, build one ``request`` event, and call
    ``Authorizer::is_authorized``. Prefer :class:`NativeAuthorizer` for repeated
    decisions so parse/lower work happens once.
    """
    require_available()
    return _dogwood_native.authorize_request(
        policy_source,
        policy_schema_source,
        action,
        principal,
        resource,
        json.dumps(input),
        event_schema_source,
    )
