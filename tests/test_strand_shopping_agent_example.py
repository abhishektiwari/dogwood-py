import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dogwood import native
from dogwood.integrations.strands import DogwoodPlugin
from examples.strands_shopping_agent.cart_store import (
    CART_ITEMS,
    cart_policy_context,
    shopping_cart_id,
)
from examples.strands_shopping_agent.console import requested_item
from examples.strands_shopping_agent.policy_runtime import (
    apply_shopping_precheck,
    build_shopping_tool_event,
    next_tool_sequence,
    policy_hint,
    shopping_interventions,
    shopping_tool_precheck,
)
from examples.strands_shopping_agent.tools import (
    add_to_cart,
    checkout_cart,
    get_shopping_cart,
)


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "shopping_agent_policies"
SCHEMA_SOURCE = (EXAMPLES_DIR / "schema.cedarschema").read_text()
EVENT_SCHEMA_SOURCE = (EXAMPLES_DIR / "event.dwschema").read_text()
RISK_MAPPING = json.loads((EXAMPLES_DIR / "risk-mapping.json").read_text())
PRODUCTS = json.loads((EXAMPLES_DIR / "products.json").read_text())


def tool_call(
    tool: str,
    *,
    user: str = "alice",
    session_id: str = "session-1",
    cart_id: str = "cart-1",
    item_id: str = "developer-laptop",
    amount: int | None = None,
    quantity: int = 1,
    risk: int | None = None,
    status: str = "requested",
    tool_use_id: str = "tool-use",
) -> SimpleNamespace:
    product = PRODUCTS.get(item_id, {"category": "unknown", "price": 0})
    category = str(product["category"])
    risk_score = RISK_MAPPING.get(category, 100) if risk is None else risk
    amount_value = int(product["price"]) * quantity if amount is None else amount
    return SimpleNamespace(
        tool_use={
            "name": tool,
            "input": {
                "user": user,
                "session_id": session_id,
                "cart_id": cart_id,
                "item_id": item_id,
                "category": category,
                "amount": amount_value,
                "quantity": quantity,
                "risk": risk_score,
                "status": status,
            },
            "toolUseId": tool_use_id,
        },
        invocation_state={
            "principal": f'Drupe::OAuthUser::"{user}"',
            "resource": 'Drupe::Gateway::"shopping-agent"',
            "session_id": session_id,
        },
    )


def decision_for(plugin: DogwoodPlugin, event: SimpleNamespace) -> str:
    plugin.on_before_tool_call(event)
    return "Deny" if hasattr(event, "cancel_tool") else "Allow"


def decisions_for(policy_file: str, tools: list[str]) -> list[str]:
    return decisions_for_events(
        policy_file,
        [tool_call(tool, tool_use_id=f"{policy_file}-{i}") for i, tool in enumerate(tools)],
    )


def decisions_for_events(policy_file: str, events: list[object]) -> list[str]:
    plugin = DogwoodPlugin(
        policy_source=(EXAMPLES_DIR / policy_file).read_text(),
        policy_schema_source=SCHEMA_SOURCE,
        event_schema_source=EVENT_SCHEMA_SOURCE,
    )
    return [decision_for(plugin, event) for event in events]


def test_shopping_agent_policy_examples():
    if not native.available():
        pytest.skip("native extension is not built")

    assert decisions_for_events(
        "daily_budget.dw",
        [
            tool_call("checkout_cart", amount=20, tool_use_id="budget-1"),
            tool_call("checkout_cart", amount=20, tool_use_id="budget-2"),
            tool_call("checkout_cart", amount=20, tool_use_id="budget-3"),
        ],
    ) == [
        "Allow",
        "Allow",
        "Allow",
    ]
    assert decisions_for_events(
        "daily_budget.dw",
        [
            tool_call("checkout_cart", amount=20, status="completed", tool_use_id="budget-completed-1"),
            tool_call("checkout_cart", amount=20, status="completed", tool_use_id="budget-completed-2"),
            tool_call("checkout_cart", amount=20, status="completed", tool_use_id="budget-completed-3"),
        ],
    ) == [
        "Allow",
        "Allow",
        "Deny",
    ]
    assert decisions_for_events(
        "daily_order_quota.dw",
        [
            tool_call("checkout_cart", amount=1, tool_use_id="quota-1"),
            tool_call("checkout_cart", amount=1, tool_use_id="quota-2"),
            tool_call("checkout_cart", amount=1, tool_use_id="quota-3"),
        ],
    ) == [
        "Allow",
        "Allow",
        "Allow",
    ]
    assert decisions_for_events(
        "daily_order_quota.dw",
        [
            tool_call("checkout_cart", amount=1, status="completed", tool_use_id="quota-completed-1"),
            tool_call("checkout_cart", amount=1, status="completed", tool_use_id="quota-completed-2"),
            tool_call("checkout_cart", amount=1, status="completed", tool_use_id="quota-completed-3"),
        ],
    ) == [
        "Allow",
        "Allow",
        "Deny",
    ]
    assert decisions_for_events(
        "approval_gate.dw",
        [
            tool_call("checkout_cart", tool_use_id="approval-1"),
            tool_call("approve_checkout", status="approved", tool_use_id="approval-2"),
            tool_call("checkout_cart", tool_use_id="approval-3"),
        ],
    ) == [
        "Deny",
        "Deny",
        "Allow",
    ]
    assert decisions_for(
        "session_access.dw",
        [
            "get_shopping_cart",
            "grant_session",
            "get_shopping_cart",
            "revoke_session",
            "get_shopping_cart",
        ],
    ) == [
        "Deny",
        "Deny",
        "Allow",
        "Deny",
        "Deny",
    ]
    assert decisions_for("tool_sequence.dw", ["checkout_cart", "add_to_cart", "checkout_cart"]) == [
        "Deny",
        "Deny",
        "Allow",
    ]
    assert decisions_for_events(
        "item_risk_guardrail.dw",
        [
            tool_call("add_to_cart", item_id="clean-code-book", tool_use_id="risk-1"),
            tool_call("add_to_cart", item_id="iphone17", tool_use_id="risk-2"),
            tool_call("approve_step_up", item_id="iphone17", status="approved", tool_use_id="risk-3"),
            tool_call("add_to_cart", item_id="iphone17", tool_use_id="risk-4"),
            tool_call("checkout_cart", item_id="clean-code-book", tool_use_id="risk-5"),
            tool_call("checkout_cart", item_id="iphone17", tool_use_id="risk-6"),
        ],
    ) == [
        "Allow",
        "Deny",
        "Deny",
        "Allow",
        "Allow",
        "Allow",
    ]
    assert decisions_for(
        "session_login.dw",
        ["get_shopping_cart", "login", "get_shopping_cart"],
    ) == [
        "Deny",
        "Deny",
        "Allow",
    ]


def test_strands_shopping_agent_tool_use_id_is_derived_from_session_context():
    event = build_shopping_tool_event(
        "checkout_cart",
        user="alice",
        session_id="session-123",
        cart_id="cart-456",
    )

    tool_use_id = event.tool_use["toolUseId"]
    assert tool_use_id.startswith("tooluse_checkout_cart_")
    assert tool_use_id.removeprefix("tooluse_checkout_cart_").isdigit()


def test_strands_shopping_agent_tool_use_id_increments_per_tool():
    counts: dict[str, int] = {}

    first_add_sequence = next_tool_sequence(counts, "add_to_cart")
    second_add_sequence = next_tool_sequence(counts, "add_to_cart")
    checkout_sequence = next_tool_sequence(counts, "checkout_cart")
    first_add = build_shopping_tool_event(
        "add_to_cart",
        user="alice",
        session_id="session-123",
        cart_id="cart-456",
        sequence=first_add_sequence,
    ).tool_use["toolUseId"]
    second_add = build_shopping_tool_event(
        "add_to_cart",
        user="alice",
        session_id="session-123",
        cart_id="cart-456",
        sequence=second_add_sequence,
    ).tool_use["toolUseId"]
    checkout = build_shopping_tool_event(
        "checkout_cart",
        user="alice",
        session_id="session-123",
        cart_id="cart-456",
        sequence=checkout_sequence,
    ).tool_use["toolUseId"]

    assert first_add.startswith("tooluse_add_to_cart_")
    assert second_add.startswith("tooluse_add_to_cart_")
    assert checkout.startswith("tooluse_checkout_cart_")
    assert first_add != second_add


def test_strands_shopping_agent_cart_tracks_items_by_session():
    user = "cart-test-user"
    session_id = "session-cart-test"
    cart_id = shopping_cart_id(user, session_id)
    CART_ITEMS.pop(cart_id, None)

    assert "items: empty" in get_shopping_cart(user, session_id)

    add_to_cart(cart_id, "clean-code-book", 2)
    cart = get_shopping_cart(user, session_id)

    assert "clean-code-book x 2 @ $20 = $40" in cart
    assert "total=$40" in cart

    order = checkout_cart(user, session_id)

    assert "clean-code-book x 2 @ $20 = $40" in order
    assert "items: empty" in get_shopping_cart(user, session_id)


def test_strands_shopping_agent_cart_policy_context_uses_cart_total_and_highest_risk():
    user = "cart-policy-user"
    session_id = "session-cart-policy"
    cart_id = shopping_cart_id(user, session_id)
    CART_ITEMS.pop(cart_id, None)

    add_to_cart(cart_id, "clean-code-book", 2)
    add_to_cart(cart_id, "iphone17", 1)

    context = cart_policy_context(cart_id, "clean-code-book")

    assert context["amount"] == 1339
    assert context["quantity"] == 3
    assert context["item_id"] == "iphone17"
    assert context["risk"] == 100


def test_strands_shopping_agent_policy_hints_are_loaded_from_policy_annotations():
    assert "grant" in policy_hint("session_access.dw")
    assert "login" in policy_hint("session_login.dw")
    assert "quota" in policy_hint("daily_order_quota.dw")


def test_strands_shopping_agent_precheck_blocks_empty_checkout_before_policy():
    user = "precheck-user"
    session_id = "precheck-session"
    cart_id = shopping_cart_id(user, session_id)
    CART_ITEMS.pop(cart_id, None)

    event = build_shopping_tool_event(
        "checkout_cart",
        user=user,
        session_id=session_id,
        cart_id=cart_id,
    )

    decision = shopping_tool_precheck(event)

    assert decision.__class__.__name__.endswith("Guide")
    assert getattr(decision, "feedback", None) == "The cart is empty. Add an item before checkout."
    assert apply_shopping_precheck(event) == "The cart is empty. Add an item before checkout."


def test_strands_shopping_agent_precheck_allows_checkout_with_items():
    user = "precheck-user-with-cart"
    session_id = "precheck-session-with-cart"
    cart_id = shopping_cart_id(user, session_id)
    CART_ITEMS.pop(cart_id, None)
    add_to_cart(cart_id, "iphone17-case", 1)

    event = build_shopping_tool_event(
        "checkout_cart",
        user=user,
        session_id=session_id,
        cart_id=cart_id,
    )

    assert shopping_tool_precheck(event).__class__.__name__.endswith("Proceed")
    assert apply_shopping_precheck(event) is None


def test_strands_shopping_agent_precheck_transforms_model_tool_input():
    event = SimpleNamespace(
        tool_use={
            "name": "add_to_cart",
            "input": {
                "user": "transform-user",
                "session_id": "transform-session",
                "item_id": "IPHONE17 Case",
                "quantity": "2",
            },
            "toolUseId": "tooluse_add_to_cart_1",
        }
    )

    decision = shopping_tool_precheck(event)

    assert decision.__class__.__name__.endswith("Transform")
    assert apply_shopping_precheck(event) is None
    assert event.tool_use["input"]["item_id"] == "iphone17-case"
    assert event.tool_use["input"]["quantity"] == 2
    assert event.tool_use["input"]["cart_id"] == "cart-transform-user-transform-session"


def test_strands_shopping_agent_requested_item_preserves_unknown_product():
    assert requested_item(["iphone18-case", "1"], "developer-laptop") == "iphone18-case"


def test_strands_shopping_agent_precheck_guides_unknown_product():
    event = build_shopping_tool_event("add_to_cart", item_id="iphone18-case", quantity=1)

    message = apply_shopping_precheck(event)

    assert message is not None
    assert "Choose one of these product ids:" in message
    assert "iphone17-case" in message


def test_strands_shopping_agent_interventions_start_with_precheck():
    interventions = shopping_interventions()

    assert interventions[0].name == "shopping-tool-precheck"
    assert all(
        getattr(intervention, "name", "") == "dogwood-policy"
        for intervention in interventions[1:]
    )
