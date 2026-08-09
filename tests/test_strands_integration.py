from pathlib import Path
from types import SimpleNamespace

import pytest

from dogwood import native
from dogwood.integrations.strands import (
    DogwoodIntervention,
    DogwoodPlugin,
    StrandsPolicyHook,
    default_tool_input,
)


class FakeAuthorizer:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def authorize_request(self, action, principal, resource, input):
        self.calls.append((action, principal, resource, input))
        return self.decision


def test_strands_policy_hook_allows_tool_call():
    authorizer = FakeAuthorizer("Allow")
    event = SimpleNamespace(
        tool_use={"name": "search", "input": {"query": "dogwood"}, "toolUseId": "t1"},
        invocation_state={
            "principal": 'Drupe::OAuthUser::"alice"',
            "resource": 'Drupe::Gateway::"agent"',
        },
    )

    hook = StrandsPolicyHook(authorizer=authorizer)
    hook(event)

    assert not hasattr(event, "cancel_tool")
    assert authorizer.calls == [
        (
            "Drupe::Action::CallTool",
            'Drupe::OAuthUser::"alice"',
            'Drupe::Gateway::"agent"',
            {
                "tool": "search",
                "input": {"query": "dogwood"},
                "toolUseId": "t1",
            },
        )
    ]


def test_strands_policy_hook_denies_tool_call():
    event = SimpleNamespace(tool_use={"name": "delete_file", "input": {}})
    hook = StrandsPolicyHook(
        authorizer=FakeAuthorizer("Deny"),
        deny_message="Denied by Dogwood.",
    )

    hook(event)

    assert event.cancel_tool == "Denied by Dogwood."


def test_default_tool_input_handles_object_tool_use():
    event = SimpleNamespace(
        tool_use=SimpleNamespace(name="lookup", input={"id": "123"}, tool_use_id="abc")
    )

    assert default_tool_input(event) == {
        "tool": "lookup",
        "input": {"id": "123"},
        "toolUseId": "abc",
    }


def test_dogwood_intervention_returns_proceed_for_allowed_tool_call():
    intervention = DogwoodIntervention(authorizer=FakeAuthorizer("Allow"))
    event = SimpleNamespace(tool_use={"name": "search", "input": {}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Proceed")
    assert intervention.policy_hook.authorizer.calls == [
        (
            "Drupe::Action::CallTool",
            'Drupe::OAuthUser::"agent"',
            'Drupe::Gateway::"agent"',
            {
                "tool": "search",
                "input": {},
                "toolUseId": "",
            },
        )
    ]


def test_dogwood_intervention_returns_deny_for_denied_tool_call():
    intervention = DogwoodIntervention(
        authorizer=FakeAuthorizer("Deny"),
        deny_message="Denied by Dogwood.",
    )
    event = SimpleNamespace(tool_use={"name": "write_file", "input": {"path": "/tmp/x"}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Deny")
    assert getattr(decision, "reason", None) == "Denied by Dogwood."


def test_dogwood_intervention_returns_confirm_for_confirmable_denied_tool_call():
    intervention = DogwoodIntervention(
        authorizer=FakeAuthorizer("Deny"),
        confirm_when=lambda event: event.tool_use["name"] == "add_to_cart",
        confirm_prompt="Approve high-risk cart item?",
    )
    event = SimpleNamespace(tool_use={"name": "add_to_cart", "input": {"item_id": "iphone17"}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Confirm")
    assert getattr(decision, "prompt", None) == "Approve high-risk cart item?"


def test_dogwood_plugin_auto_hook_denies_tool_call():
    plugin = DogwoodPlugin(
        authorizer=FakeAuthorizer("Deny"),
        deny_message="Denied by Dogwood.",
    )
    event = SimpleNamespace(tool_use={"name": "delete_file", "input": {}})

    plugin.on_before_tool_call(event)

    assert event.cancel_tool == "Denied by Dogwood."


def test_dogwood_plugin_default_action_matches_native_authorizer():
    if not native.available():
        pytest.skip("native extension is not built")

    examples_dir = Path(__file__).resolve().parents[1] / "examples" / "shopping_agent_policies"
    plugin = DogwoodPlugin(
        policy_source=(examples_dir / "daily_budget.dw").read_text(),
        policy_schema_source=(examples_dir / "schema.cedarschema").read_text(),
    )

    allowed_event = SimpleNamespace(
        tool_use={
            "name": "checkout_cart",
            "input": {
                "user": "alice",
                "session_id": "demo-session",
                "cart_id": "cart-1",
                "item_id": "demo-item",
                "category": "demo",
                "amount": 20,
                "quantity": 1,
                "risk": 0,
                "status": "requested",
            },
            "toolUseId": "tool-use-1",
        },
        invocation_state={
            "principal": 'Drupe::OAuthUser::"alice"',
            "resource": 'Drupe::Gateway::"agent"',
        },
    )
    denied_event = SimpleNamespace(
        tool_use={
            "name": "checkout_cart",
            "input": {
                "user": "alice",
                "session_id": "demo-session",
                "cart_id": "cart-1",
                "item_id": "demo-item",
                "category": "demo",
                "amount": 40,
                "quantity": 1,
                "risk": 0,
                "status": "requested",
            },
            "toolUseId": "tool-use-2",
        },
        invocation_state={
            "principal": 'Drupe::OAuthUser::"alice"',
            "resource": 'Drupe::Gateway::"agent"',
        },
    )

    plugin.on_before_tool_call(allowed_event)
    plugin.on_before_tool_call(denied_event)

    assert not hasattr(allowed_event, "cancel_tool")
    assert denied_event.cancel_tool == "Dogwood policy denied this tool call."
