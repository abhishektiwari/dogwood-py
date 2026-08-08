"""Use dogwood-py as a Python SDK.

Run from the repository root:

    PYTHONPATH=src python examples/api_usage.py
"""

from dogwood import Authorizer, Event, LoweredPolicySet, PolicySchema, ServiceSchema, Validator


POLICY = """
@id("sell_small_only")
permit (
    principal,
    action == Drupe::Action::"SellShares",
    resource
)
when { context.input.shares <= 50 };
"""


def sell_request(user: str, shares: int, stock: str) -> Event:
    return (
        Event.builder('Drupe::Action::"SellShares"', "request")
        .principal(f'Drupe::OAuthUser::"{user}"')
        .resource('Drupe::Gateway::"trading"')
        .field("input", "shares", shares)
        .field("input", "stock", stock)
        .request_context("input", "shares", shares)
        .request_context("input", "stock", stock)
        .build()
    )


def main() -> None:
    service_schema = ServiceSchema.defaults()
    policy_schema = PolicySchema.from_cedarschema_str("")
    policies = LoweredPolicySet.from_str(POLICY, service_schema, policy_schema)

    validation = Validator().validate(policies)
    if not validation.validation_passed():
        raise SystemExit("\n".join(validation.errors))

    authorizer = Authorizer(policies)
    for event in [
        sell_request("alice", 25, "AMZN"),
        sell_request("bob", 500, "MSFT"),
    ]:
        response = authorizer.is_authorized(event)
        decision = response.decision.value if response is not None else "No decision"
        print(f"{event.principal()} selling {event.field('input', 'shares')} shares: {decision}")


if __name__ == "__main__":
    main()
