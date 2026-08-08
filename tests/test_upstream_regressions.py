import pytest

from dogwood import LoweredPolicySet, PolicySchema, native, parse_trace
from dogwood.errors import ParseError


SIMPLE_POLICY = '''
@id("sell_small_only")
permit (
    principal,
    action == Drupe::Action::"SellShares",
    resource
)
when { context.input.shares <= 50 };
'''


TEMPORAL_POLICY = '''
@id("sell_after_prior_small_sell")
permit (
    principal,
    action == Drupe::Action::"SellShares",
    resource
)
when temporal {
    formerly within 1h Drupe::Action::"SellShares"::request{ input.stock: context.input.stock }
};
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


def require_native():
    if not native.available():
        pytest.skip("native extension is not built")


def test_bom_prefixed_cedarschema_lowers_with_native_extension():
    require_native()

    cedar = native.lower_to_cedar(SIMPLE_POLICY, "\ufeff" + SCHEMA)
    assert '@id("sell_small_only")' in cedar


@pytest.mark.parametrize("line", ["@0 )(", "@0 )text(", "@5 abc)(def", "@1 ))((", "@2 )"])
def test_malformed_trace_lines_raise_parse_error(line):
    with pytest.raises(ParseError):
        parse_trace(line)


def test_deeply_nested_trace_value_is_clean_error_not_crash():
    depth = 2_000
    nested = "[" * depth + "]" * depth
    line = f'@0 Drupe::Action::"SellShares"::request(input: {nested})'

    with pytest.raises(ParseError):
        parse_trace(line)


def test_shallow_nested_trace_value_still_parses():
    line = '@0 Drupe::Action::"SellShares"::request(input: { meta: [1, 2, { label: "ok" }] })'
    events = parse_trace(line)
    assert len(events) == 1
    assert events[0].field("input", "meta") == [1, 2, {"label": "ok"}]


def test_native_augmented_schema_export_contains_temporal_context_field():
    require_native()

    policies = LoweredPolicySet.from_str(TEMPORAL_POLICY, policy_schema=PolicySchema(SCHEMA))
    exported = policies.cedar_schema()

    assert "SellShares" in exported
    assert "policy_0__temporal_0" in exported
    assert "Bool" in exported

    round_tripped = native.lower_to_cedar(SIMPLE_POLICY, exported)
    assert '@id("sell_small_only")' in round_tripped
