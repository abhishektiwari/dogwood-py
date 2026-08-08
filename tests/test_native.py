from unittest.mock import patch

import pytest

from dogwood import LoweredPolicySet, PolicySchema, native


POLICY = '''
@id("sell_small_only")
permit (
    principal,
    action == Drupe::Action::"SellShares",
    resource
)
when { context.input.shares <= 50 };
'''


SCHEMA = """
namespace Drupe {
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


def test_schema_backed_lowering_requires_native_extension():
    with patch("dogwood.native.available", return_value=False):
        with pytest.raises(RuntimeError, match="native extension is required"):
            LoweredPolicySet.from_str(POLICY, policy_schema=PolicySchema(SCHEMA))
