from unittest.mock import patch

import pytest

from dogwood import LoweredPolicySet, PolicySchema, ServiceSchema, native


POLICY = '''
@id("sell_small_only")
permit (
    principal,
    action == Agent::Action::"SellShares",
    resource
)
when { context.input.shares <= 50 };
'''


SCHEMA = """
namespace Agent {
  type SellSharesInput = {
    shares: Long,
    stock: String
  };

  type SellSharesOutput = {
    proceeds: decimal
  };

  type SystemContext = {
    now: datetime
  };

  entity Gateway;

  entity IamEntity = {
    id: String
  };

  entity OAuthUser = {
    id: String
  } tags String;

  entity UnauthenticatedUser;

  action "CallTool" appliesTo {
    principal: [OAuthUser, IamEntity, UnauthenticatedUser],
    resource: [Gateway],
    context: {
      system: SystemContext
    }
  };

  action "SellShares" in [Action::"CallTool"] appliesTo {
    principal: [IamEntity, OAuthUser, UnauthenticatedUser],
    resource: [Gateway],
    context: {
      input: SellSharesInput,
      output?: SellSharesOutput,
      system: SystemContext
    }
  };
}
"""


EVENT_SCHEMA = """
decision event <A>::request {
    ...inputs(A),
    pin callerPrincipal: principalType(A) = principal,
    callerResource: resourceType(A),
    requestId: String,
    sessionId: String,
}

event <A>::response {
    ...inputs(A),
    ...outputs(A),
    pin callerPrincipal: principalType(A) = principal,
    callerResource: resourceType(A),
    requestId: String,
    sessionId: String,
}
"""


def test_native_lower_and_validate_with_real_schema():
    if not native.available():
        pytest.skip("native extension is not built")

    cedar = native.lower_to_cedar(POLICY, SCHEMA)
    assert '@id("sell_small_only")' in cedar
    assert "context.input" in cedar
    assert "shares" in cedar
    assert "<= 50" in cedar

    result = native.validate_policy(POLICY, SCHEMA)
    assert result["passed"] is True
    assert result["errors"] == []


def test_native_accepts_explicit_event_schema():
    if not native.available():
        pytest.skip("native extension is not built")

    authorizer = native.NativeAuthorizer(POLICY, SCHEMA, EVENT_SCHEMA)

    assert (
        authorizer.authorize_request(
            "Agent::Action::SellShares",
            'Agent::OAuthUser::"alice"',
            'Agent::Gateway::"trading"',
            {"shares": 25, "stock": "AMZN"},
        )
        == "Allow"
    )
    assert native.validate_policy(POLICY, SCHEMA, EVENT_SCHEMA)["passed"] is True


def test_schema_backed_sdk_accepts_explicit_event_schema():
    if not native.available():
        pytest.skip("native extension is not built")

    policies = LoweredPolicySet.from_str(
        POLICY,
        service_schema=ServiceSchema(event_schema=EVENT_SCHEMA),
        policy_schema=PolicySchema(SCHEMA),
    )

    assert '@id("sell_small_only")' in policies.as_cedar()
    assert policies.cedar_schema()


def test_schema_backed_lowering_requires_native_extension():
    with patch("dogwood.native.available", return_value=False):
        with pytest.raises(RuntimeError, match="native extension is required"):
            LoweredPolicySet.from_str(POLICY, policy_schema=PolicySchema(SCHEMA))
