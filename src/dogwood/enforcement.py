"""SDK-level enforcement modes for Dogwood authorization decisions.

The Rust Dogwood core evaluates policy and returns a policy decision. This
module adds Python SDK rollout behavior around that decision: enforce denials,
or run in log-only mode and report what would have happened.

Behavior matrix:

+------------------+-------------+---------------------------+
| Dogwood decision | SDK mode    | Enforcement result        |
+==================+=============+===========================+
| ``Allow``        | ``enforce`` | ``allowed=True``          |
+------------------+-------------+---------------------------+
| ``Deny``         | ``enforce`` | ``allowed=False``         |
+------------------+-------------+---------------------------+
| ``Allow``        | ``log_only``| ``allowed=True``          |
+------------------+-------------+---------------------------+
| ``Deny``         | ``log_only``| ``allowed=True``,         |
|                  |             | ``would_have_denied=True``|
+------------------+-------------+---------------------------+
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EnforcementMode = Literal["enforce", "log_only"]


@dataclass(frozen=True)
class EnforcementResult:
    """Effective SDK decision for an evaluated Dogwood event or request.

    ``decision`` is the raw Dogwood policy result, usually ``"Allow"`` or
    ``"Deny"``. ``allowed`` is the effective SDK outcome after applying
    ``mode``. In ``log_only`` mode, a Dogwood denial produces
    ``allowed=True`` and ``would_have_denied=True``.
    """

    decision: str | None
    mode: EnforcementMode
    allowed: bool
    policy_allowed: bool | None
    would_have_denied: bool
    response: Any = None

    def denied(self) -> bool:
        """Return true when the effective SDK outcome blocks the operation."""
        return not self.allowed


class PolicyEnforcer:
    """Apply ``enforce`` or ``log_only`` behavior to Dogwood decisions.

    Wrap either the Python fallback ``Authorizer`` or native authorizer-like
    objects. The wrapped authorizer still performs the Dogwood policy
    evaluation; this class only decides how that result affects the caller.
    """

    def __init__(self, authorizer: Any, mode: str = "enforce"):
        self.authorizer = authorizer
        self.mode = normalize_mode(mode)

    def authorize(self, event: Any) -> EnforcementResult:
        """Authorize an SDK ``Event`` using ``authorizer.is_authorized``."""
        if not hasattr(self.authorizer, "is_authorized"):
            raise TypeError("authorizer must provide is_authorized(event)")
        response = self.authorizer.is_authorized(event)
        return apply_enforcement(response, self.mode)

    def is_authorized(self, event: Any) -> EnforcementResult:
        """Alias for :meth:`authorize` for ``Authorizer``-like usage."""
        return self.authorize(event)

    def authorize_request(
        self,
        action: str,
        principal: str,
        resource: str,
        input: dict[str, Any],
    ) -> EnforcementResult:
        """Authorize a native-style request using ``authorize_request``."""
        if not hasattr(self.authorizer, "authorize_request"):
            raise TypeError("authorizer must provide authorize_request(action, principal, resource, input)")
        response = self.authorizer.authorize_request(action, principal, resource, input)
        return apply_enforcement(response, self.mode)


def apply_enforcement(response: Any, mode: str = "enforce") -> EnforcementResult:
    """Return the effective SDK outcome for a raw Dogwood response."""
    normalized_mode = normalize_mode(mode)
    decision = decision_text(response)
    policy_allowed = None if decision is None else is_allowed_decision(decision)
    effective_allowed = True if policy_allowed is None else policy_allowed or normalized_mode == "log_only"
    return EnforcementResult(
        decision=decision,
        mode=normalized_mode,
        allowed=effective_allowed,
        policy_allowed=policy_allowed,
        would_have_denied=normalized_mode == "log_only" and policy_allowed is False,
        response=response,
    )


def normalize_mode(mode: str) -> EnforcementMode:
    """Normalize SDK enforcement mode names.

    Accepts Python-style lowercase values and AWS-style uppercase values:
    ``"enforce"``, ``"log_only"``, ``"ENFORCE"``, and ``"LOG_ONLY"``.
    """
    normalized = mode.lower()
    if normalized not in {"enforce", "log_only"}:
        raise ValueError("mode must be 'enforce' or 'log_only'")
    return normalized  # type: ignore[return-value]


def is_enforced(mode: str) -> bool:
    """Return true when ``mode`` enforces Dogwood denials."""
    return normalize_mode(mode) == "enforce"


def decision_text(response: Any) -> str | None:
    """Extract ``Allow`` or ``Deny`` text from common Dogwood response shapes."""
    if response is None:
        return None
    decision = getattr(response, "decision", response)
    value = getattr(decision, "value", decision)
    return str(value)


def is_allowed_decision(response: Any) -> bool:
    """Return true when a raw Dogwood response or decision is ``Allow``."""
    return decision_text(response) == "Allow"


__all__ = [
    "EnforcementMode",
    "EnforcementResult",
    "PolicyEnforcer",
    "apply_enforcement",
    "decision_text",
    "is_allowed_decision",
    "is_enforced",
    "normalize_mode",
]
