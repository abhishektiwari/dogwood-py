from pathlib import Path
from types import SimpleNamespace

import pytest

from dogwood import native
from dogwood.integrations.strands import (
    ALL_LIFECYCLE_EVENTS,
    confirm,
    deny,
    DogwoodIntervention,
    DogwoodPlugin,
    StrandsLifecyclePolicyHook,
    proceed,
    StrandsPolicyHook,
    default_lifecycle_input,
    default_tool_input,
    guide,
    transform,
)
from examples.strands_shopping_agent.config import SHOPPING_ACTION


class FakeAuthorizer:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def authorize_request(self, action, principal, resource, input):
        self.calls.append((action, principal, resource, input))
        if isinstance(self.decision, list):
            return self.decision.pop(0)
        return self.decision


def test_strands_policy_hook_allows_tool_call():
    authorizer = FakeAuthorizer("Allow")
    event = SimpleNamespace(
        tool_use={"name": "search", "input": {"query": "dogwood"}, "toolUseId": "t1"},
        invocation_state={
            "principal": 'Agent::OAuthUser::"alice"',
            "resource": 'Agent::Gateway::"agent"',
        },
    )

    hook = StrandsPolicyHook(authorizer=authorizer)
    hook(event)

    assert not hasattr(event, "cancel_tool")
    assert authorizer.calls == [
        (
            "Agent::Action::CallTool",
            'Agent::OAuthUser::"alice"',
            'Agent::Gateway::"agent"',
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


def test_strands_policy_hook_log_only_records_denial_without_canceling():
    event = SimpleNamespace(tool_use={"name": "delete_file", "input": {}})
    hook = StrandsPolicyHook(
        authorizer=FakeAuthorizer("Deny"),
        mode="log_only",
        deny_message="Denied by Dogwood.",
    )

    hook(event)

    assert not hasattr(event, "cancel_tool")
    assert event.dogwood_decision == "Deny"
    assert event.dogwood_enforcement_mode == "log_only"
    assert event.dogwood_would_have_denied is True


def test_default_tool_input_handles_object_tool_use():
    event = SimpleNamespace(
        tool_use=SimpleNamespace(name="lookup", input={"id": "123"}, tool_use_id="abc")
    )

    assert default_tool_input(event) == {
        "tool": "lookup",
        "input": {"id": "123"},
        "toolUseId": "abc",
    }


def test_default_lifecycle_input_is_json_safe():
    event = SimpleNamespace(
        dogwood_lifecycle="before_model_call",
        invocation_state={"request_id": "r1"},
        projected_input_tokens=42,
        messages=[{"role": "user", "content": object()}],
    )

    assert default_lifecycle_input(event) == {
        "lifecycle": "before_model_call",
        "invocationState": {"request_id": "r1"},
        "projected_input_tokens": 42,
        "messages": [{"role": "user", "content": str(event.messages[0]["content"])}],
    }


def test_dogwood_intervention_returns_proceed_for_allowed_tool_call():
    intervention = DogwoodIntervention(authorizer=FakeAuthorizer("Allow"))
    event = SimpleNamespace(tool_use={"name": "search", "input": {}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Proceed")
    assert intervention.policy_hook.authorizer.calls == [
        (
            "Agent::Action::CallTool",
            'Agent::OAuthUser::"agent"',
            'Agent::Gateway::"agent"',
            {
                "tool": "search",
                "input": {},
                "toolUseId": "",
            },
        )
    ]


def test_dogwood_intervention_accepts_callable_action_resolver():
    authorizer = FakeAuthorizer("Allow")
    intervention = DogwoodIntervention(
        authorizer=authorizer,
        action=lambda event: f'Demo::Action::"{event.tool_use["name"]}"',
    )
    event = SimpleNamespace(tool_use={"name": "search", "input": {}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Proceed")
    assert authorizer.calls[0][0] == 'Demo::Action::"search"'


def test_dogwood_intervention_returns_deny_for_denied_tool_call():
    intervention = DogwoodIntervention(
        authorizer=FakeAuthorizer("Deny"),
        deny_message="Denied by Dogwood.",
    )
    event = SimpleNamespace(tool_use={"name": "write_file", "input": {"path": "/tmp/x"}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Deny")
    assert getattr(decision, "reason", None) == "Denied by Dogwood."


def test_dogwood_intervention_log_only_returns_proceed_for_denied_tool_call():
    intervention = DogwoodIntervention(
        authorizer=FakeAuthorizer("Deny"),
        mode="log_only",
        deny_message="Denied by Dogwood.",
    )
    event = SimpleNamespace(tool_use={"name": "write_file", "input": {"path": "/tmp/x"}})

    decision = intervention.before_tool_call(event)

    assert decision.__class__.__name__.endswith("Proceed")
    assert event.dogwood_decision == "Deny"
    assert event.dogwood_enforcement_mode == "log_only"
    assert event.dogwood_would_have_denied is True


def test_dogwood_intervention_supports_before_invocation_lifecycle():
    intervention = DogwoodIntervention(
        authorizer=FakeAuthorizer("Deny"),
        lifecycle_events="all",
        deny_message="Invocation denied by Dogwood.",
    )
    event = SimpleNamespace(invocation_state={"request_id": "r1"})

    decision = intervention.before_invocation(event)

    assert decision.__class__.__name__.endswith("Deny")
    assert getattr(decision, "reason", None) == "Invocation denied by Dogwood."
    assert intervention.policy_hook.authorizer.calls == [
        (
            "Agent::Action::CallTool",
            'Agent::OAuthUser::"agent"',
            'Agent::Gateway::"agent"',
            {
                "lifecycle": "before_invocation",
                "invocationState": {"request_id": "r1"},
            },
        )
    ]


def test_dogwood_intervention_supports_model_and_after_tool_lifecycles():
    intervention = DogwoodIntervention(
        authorizer=FakeAuthorizer(["Deny", "Allow", "Deny"]),
        lifecycle_events="all",
        deny_message="Model output needs revision.",
    )

    before_model = intervention.before_model_call(
        SimpleNamespace(projected_input_tokens=100)
    )
    after_tool = intervention.after_tool_call(
        SimpleNamespace(tool_use={"name": "checkout_cart", "input": {"status": "completed"}})
    )
    after_model = intervention.after_model_call(SimpleNamespace(message={"content": "done"}))

    assert before_model.__class__.__name__.endswith("Deny")
    assert after_tool.__class__.__name__.endswith("Proceed")
    assert after_model.__class__.__name__.endswith("Guide")
    assert getattr(after_model, "feedback", None) == "Model output needs revision."


def test_strands_action_helpers_return_typed_decisions():
    def redact(event):
        event.tool_use["input"]["body"] = "redacted"

    proceed_decision = proceed()
    deny_decision = deny("Blocked.")
    confirm_decision = confirm("Approve?")
    guide_decision = guide("Include a subject before sending email.")
    transform_decision = transform(redact)

    assert proceed_decision.__class__.__name__.endswith("Proceed")
    assert deny_decision.__class__.__name__.endswith("Deny")
    assert getattr(deny_decision, "reason", None) == "Blocked."
    assert confirm_decision.__class__.__name__.endswith("Confirm")
    assert getattr(confirm_decision, "prompt", None) == "Approve?"
    assert guide_decision.__class__.__name__.endswith("Guide")
    assert getattr(guide_decision, "feedback", None) == "Include a subject before sending email."
    assert transform_decision.__class__.__name__.endswith("Transform")
    assert getattr(transform_decision, "apply", None) is redact


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


def test_dogwood_plugin_log_only_does_not_cancel_tool_call():
    plugin = DogwoodPlugin(
        authorizer=FakeAuthorizer("Deny"),
        mode="log_only",
        deny_message="Denied by Dogwood.",
    )
    event = SimpleNamespace(tool_use={"name": "delete_file", "input": {}})

    plugin.on_before_tool_call(event)

    assert not hasattr(event, "cancel_tool")
    assert event.dogwood_decision == "Deny"
    assert event.dogwood_would_have_denied is True


def test_lifecycle_policy_hook_supports_every_lifecycle_event():
    hook = StrandsLifecyclePolicyHook(
        authorizer=FakeAuthorizer(["Deny"] * len(ALL_LIFECYCLE_EVENTS)),
        lifecycle_events="all",
        deny_message="Denied by Dogwood.",
    )

    events = {
        "before_invocation": SimpleNamespace(invocation_state={"request_id": "r1"}),
        "after_invocation": SimpleNamespace(result="done"),
        "message_added": SimpleNamespace(message={"role": "assistant"}),
        "before_model_call": SimpleNamespace(projected_input_tokens=10),
        "after_model_call": SimpleNamespace(message={"role": "assistant"}),
        "before_tool_call": SimpleNamespace(tool_use={"name": "search", "input": {}}),
        "after_tool_call": SimpleNamespace(tool_use={"name": "search", "input": {}}),
    }

    for lifecycle in ALL_LIFECYCLE_EVENTS:
        assert hook.handle(lifecycle, events[lifecycle]) == "Deny"

    assert events["before_invocation"].cancel == "Denied by Dogwood."
    assert events["before_model_call"].cancel == "Denied by Dogwood."
    assert events["before_tool_call"].cancel_tool == "Denied by Dogwood."
    assert not hasattr(events["after_invocation"], "cancel")
    assert not hasattr(events["after_tool_call"], "cancel_tool")
    assert len(hook.authorizer.calls) == len(ALL_LIFECYCLE_EVENTS)


def test_dogwood_plugin_registers_lifecycle_methods():
    plugin = DogwoodPlugin(
        authorizer=FakeAuthorizer(["Deny"] * len(ALL_LIFECYCLE_EVENTS)),
        lifecycle_events="all",
        deny_message="Denied by Dogwood.",
    )

    before_invocation = SimpleNamespace(invocation_state={})
    after_invocation = SimpleNamespace(result="done")
    message_added = SimpleNamespace(message={"role": "user"})
    before_model = SimpleNamespace(projected_input_tokens=5)
    after_model = SimpleNamespace(message={"role": "assistant"})
    before_tool = SimpleNamespace(tool_use={"name": "search", "input": {}})
    after_tool = SimpleNamespace(tool_use={"name": "search", "input": {}})

    plugin.on_before_invocation(before_invocation)
    plugin.on_after_invocation(after_invocation)
    plugin.on_message_added(message_added)
    plugin.on_before_model_call(before_model)
    plugin.on_after_model_call(after_model)
    plugin.on_before_tool_call(before_tool)
    plugin.on_after_tool_call(after_tool)

    assert before_invocation.cancel == "Denied by Dogwood."
    assert before_model.cancel == "Denied by Dogwood."
    assert before_tool.cancel_tool == "Denied by Dogwood."
    assert len(plugin.lifecycle_hook.authorizer.calls) == len(ALL_LIFECYCLE_EVENTS)


def test_dogwood_plugin_supports_callable_action_with_native_authorizer():
    if not native.available():
        pytest.skip("native extension is not built")

    examples_dir = Path(__file__).resolve().parents[1] / "examples" / "shopping_agent_policies"
    plugin = DogwoodPlugin(
        policy_source=(examples_dir / "daily_budget.dw").read_text(),
        policy_schema_source=(examples_dir / "schema.cedarschema").read_text(),
        event_schema_source=(examples_dir / "event.dwschema").read_text(),
        action=SHOPPING_ACTION,
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
                "status": "completed",
            },
            "toolUseId": "tool-use-1",
        },
        invocation_state={
            "principal": 'Agent::OAuthUser::"alice"',
            "resource": 'Agent::Gateway::"agent"',
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
                "status": "completed",
            },
            "toolUseId": "tool-use-2",
        },
        invocation_state={
            "principal": 'Agent::OAuthUser::"alice"',
            "resource": 'Agent::Gateway::"agent"',
        },
    )

    plugin.on_before_tool_call(allowed_event)
    plugin.on_before_tool_call(denied_event)

    assert not hasattr(allowed_event, "cancel_tool")
    assert denied_event.cancel_tool == "Dogwood policy denied this tool call."
