from types import SimpleNamespace

import pytest

from dogwood import (
    Authorizer,
    Decision,
    EnforcementResult,
    Event,
    LoweredPolicySet,
    PolicyEnforcer,
    apply_enforcement,
)


DENY_POLICY = '''
@id("deny_large")
permit (principal, action == Agent::Action::"Buy", resource)
when { context.input.amount <= 50 };
'''


def buy_event(amount: int, kind: str = "request") -> Event:
    return (
        Event.builder('Agent::Action::"Buy"', kind)
        .principal('Agent::OAuthUser::"alice"')
        .resource('Agent::Gateway::"shop"')
        .field("input", "amount", amount)
        .request_context("input", "amount", amount)
        .build()
    )


def test_policy_enforcer_enforce_denies_policy_denial():
    enforcer = PolicyEnforcer(Authorizer(LoweredPolicySet.from_str(DENY_POLICY)))

    result = enforcer.authorize(buy_event(75))

    assert isinstance(result, EnforcementResult)
    assert result.decision == "Deny"
    assert result.mode == "enforce"
    assert result.policy_allowed is False
    assert result.allowed is False
    assert result.denied() is True
    assert result.would_have_denied is False


def test_policy_enforcer_log_only_records_policy_denial_without_blocking():
    enforcer = PolicyEnforcer(Authorizer(LoweredPolicySet.from_str(DENY_POLICY)), mode="LOG_ONLY")

    result = enforcer.is_authorized(buy_event(75))

    assert result.decision == "Deny"
    assert result.mode == "log_only"
    assert result.policy_allowed is False
    assert result.allowed is True
    assert result.denied() is False
    assert result.would_have_denied is True


def test_policy_enforcer_log_only_preserves_policy_allow():
    enforcer = PolicyEnforcer(Authorizer(LoweredPolicySet.from_str(DENY_POLICY)), mode="log_only")

    result = enforcer.authorize(buy_event(25))

    assert result.decision == "Allow"
    assert result.policy_allowed is True
    assert result.allowed is True
    assert result.would_have_denied is False


def test_policy_enforcer_allows_non_decision_events():
    enforcer = PolicyEnforcer(Authorizer(LoweredPolicySet.from_str(DENY_POLICY)))

    result = enforcer.authorize(buy_event(75, kind="response"))

    assert result.decision is None
    assert result.policy_allowed is None
    assert result.allowed is True
    assert result.would_have_denied is False


def test_policy_enforcer_supports_native_style_authorize_request():
    authorizer = SimpleNamespace(
        authorize_request=lambda action, principal, resource, input: Decision.DENY,
    )
    enforcer = PolicyEnforcer(authorizer, mode="log_only")

    result = enforcer.authorize_request(
        "Agent::Action::Buy",
        'Agent::OAuthUser::"alice"',
        'Agent::Gateway::"shop"',
        {"amount": 75},
    )

    assert result.decision == "Deny"
    assert result.allowed is True
    assert result.would_have_denied is True


def test_apply_enforcement_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode must be"):
        apply_enforcement("Deny", mode="audit")
