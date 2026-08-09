from __future__ import annotations

from types import SimpleNamespace

from dogwood.integrations.strands import DogwoodIntervention

from examples.strands_shopping_agent.cart_store import (
    cart_policy_context,
    describe_cart,
)
from examples.strands_shopping_agent.config import PRODUCTS, RISK_MAPPING
from examples.strands_shopping_agent.policy_runtime import (
    apply_shopping_precheck,
    build_shopping_tool_event,
    decision_for,
    next_tool_sequence,
    policy_allows,
    policy_hint,
    policy_intervention,
    policy_interventions,
    print_checkout_summary,
    session_access_allows,
)
from examples.strands_shopping_agent.tools import (
    add_to_cart,
    checkout_cart,
    list_products,
    remove_from_cart,
)


def check_agent_policy(policy_file: str, events: list[SimpleNamespace]) -> None:
    intervention = policy_intervention(policy_file)

    print(policy_file)
    for event in events:
        tool_name = event.tool_use["name"]
        item_id = event.tool_use["input"]["item_id"]
        status = event.tool_use["input"]["status"]
        print(f"  {tool_name}(item_id={item_id}, status={status}): {decision_for(intervention, event)}")


def check_shopping_agent_policies(user: str, session_id: str, cart_id: str, item_id: str) -> None:
    check_agent_policy(
        "approval_gate.dw",
        [
            build_shopping_tool_event(
                "checkout_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=1,
            ),
            build_shopping_tool_event(
                "approve_checkout",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                status="approved",
                sequence=1,
            ),
            build_shopping_tool_event(
                "checkout_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=2,
            ),
        ],
    )
    check_agent_policy(
        "session_access.dw",
        [
            build_shopping_tool_event(
                "get_shopping_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=1,
            ),
            build_shopping_tool_event(
                "grant_session",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                status="granted",
                sequence=1,
            ),
            build_shopping_tool_event(
                "get_shopping_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=2,
            ),
            build_shopping_tool_event(
                "revoke_session",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                status="revoked",
                sequence=1,
            ),
            build_shopping_tool_event(
                "get_shopping_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=3,
            ),
        ],
    )
    check_agent_policy(
        "tool_sequence.dw",
        [
            build_shopping_tool_event(
                "checkout_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=1,
            ),
            build_shopping_tool_event(
                "add_to_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=1,
            ),
            build_shopping_tool_event(
                "checkout_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=2,
            ),
        ],
    )
    check_agent_policy(
        "item_risk_guardrail.dw",
        [
            build_shopping_tool_event("checkout_cart", item_id="clean-code-book", sequence=1),
            build_shopping_tool_event("checkout_cart", item_id="iphone17", sequence=2),
        ],
    )
    check_agent_policy(
        "session_login.dw",
        [
            build_shopping_tool_event(
                "get_shopping_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=1,
            ),
            build_shopping_tool_event(
                "login",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                status="logged-in",
                sequence=1,
            ),
            build_shopping_tool_event(
                "get_shopping_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=item_id,
                sequence=2,
            ),
        ],
    )


def print_console_help() -> None:
    print("Commands:")
    print("  cart")
    print("  grant | revoke | login | approve | step-up")
    print("  add <item_id> [quantity]")
    print("  remove <item_id> [quantity]")
    print("  checkout")
    print("  products   # list_products")
    print("  help")
    print("  quit")


def first_known_item(words: list[str], default: str) -> str:
    for word in words:
        item = word.strip().lower()
        if item in PRODUCTS:
            return item
    return default


def parse_quantity(words: list[str], default: int = 1) -> int:
    for word in words:
        try:
            return max(1, int(word))
        except ValueError:
            continue
    return default


def record_event(
    interventions: dict[str, DogwoodIntervention],
    policy_file: str,
    tool_name: str,
    *,
    user: str,
    session_id: str,
    cart_id: str,
    item_id: str,
    quantity: int = 1,
    status: str = "requested",
    sequence: int = 1,
) -> None:
    event = build_shopping_tool_event(
        tool_name,
        user=user,
        session_id=session_id,
        cart_id=cart_id,
        item_id=item_id,
        quantity=quantity,
        status=status,
        sequence=sequence,
    )
    decision_for(interventions[policy_file], event)
    print(f"recorded: {tool_name}")


def run_interactive_console(user: str, session_id: str, cart_id: str, item_id: str) -> None:
    current_item = item_id
    interventions = policy_interventions()
    tool_use_counts: dict[str, int] = {}
    print_console_help()

    while True:
        try:
            prompt = input("shopping-agent> ").strip()
        except EOFError:
            print()
            return

        if not prompt:
            continue

        words = prompt.split()
        command = words[0].lower()

        if command in {"quit", "exit"}:
            return
        if command == "help":
            print_console_help()
            continue
        if command == "products":
            sequence = next_tool_sequence(tool_use_counts, "list_products")
            allowed = session_access_allows(
                interventions,
                "list_products",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                sequence=sequence,
            )
            print(list_products() if allowed else policy_hint("session_access.dw"))
            continue

        if command == "cart":
            print(f"user={user}")
            print(f"session_id={session_id}")
            print(f"cart_id={cart_id}")
            sequence = next_tool_sequence(tool_use_counts, "get_shopping_cart")
            allowed = session_access_allows(
                interventions,
                "get_shopping_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                sequence=sequence,
            )
            print(describe_cart(cart_id, include_cart_id=False) if allowed else policy_hint("session_access.dw"))
            continue

        if command in {"grant", "revoke", "login", "approve", "step-up"}:
            tool_name = {
                "grant": "grant_session",
                "revoke": "revoke_session",
                "approve": "approve_checkout",
                "step-up": "approve_step_up",
            }.get(command, command)
            status = {
                "grant": "granted",
                "revoke": "revoked",
                "login": "logged-in",
                "approve": "approved",
                "step-up": "approved",
            }[command]
            policy_file = {
                "grant": "session_access.dw",
                "revoke": "session_access.dw",
                "login": "session_login.dw",
                "approve": "approval_gate.dw",
                "step-up": "item_risk_guardrail.dw",
            }[command]
            sequence = next_tool_sequence(tool_use_counts, tool_name)
            record_event(
                interventions,
                policy_file,
                tool_name,
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                status=status,
                sequence=sequence,
            )
            continue

        if command == "add":
            current_item = first_known_item(words[1:], current_item)
            quantity = parse_quantity(words[1:])
            sequence = next_tool_sequence(tool_use_counts, "add_to_cart")
            if not session_access_allows(
                interventions,
                "add_to_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                quantity=quantity,
                sequence=sequence,
            ):
                print(policy_hint("session_access.dw"))
                continue

            risk_allowed = policy_allows(
                interventions,
                "item_risk_guardrail.dw",
                "add_to_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                quantity=quantity,
                sequence=sequence,
            )
            if risk_allowed:
                record_event(
                    interventions,
                    "tool_sequence.dw",
                    "add_to_cart",
                    user=user,
                    session_id=session_id,
                    cart_id=cart_id,
                    item_id=current_item,
                    quantity=quantity,
                    sequence=sequence,
                )
                print(add_to_cart(cart_id, current_item, quantity))
            else:
                category = str(PRODUCTS[current_item]["category"])
                risk = int(RISK_MAPPING.get(category, 100))
                if risk > 50:
                    print(f"step-up required: ask user to approve {current_item}, then run `step-up`")
            continue

        if command == "remove":
            current_item = first_known_item(words[1:], current_item)
            quantity = parse_quantity(words[1:])
            sequence = next_tool_sequence(tool_use_counts, "remove_from_cart")
            allowed = session_access_allows(
                interventions,
                "remove_from_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                quantity=quantity,
                sequence=sequence,
            )
            print(remove_from_cart(cart_id, current_item, quantity) if allowed else policy_hint("session_access.dw"))
            continue

        if command == "checkout":
            current_item = first_known_item(words[1:], current_item)
            policy_context = cart_policy_context(cart_id, current_item)
            sequence = next_tool_sequence(tool_use_counts, "checkout_cart")
            checkout_event = build_shopping_tool_event(
                "checkout_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=str(policy_context["item_id"]),
                amount=int(policy_context["amount"]),
                quantity=int(policy_context["quantity"]),
                risk=int(policy_context["risk"]),
                sequence=sequence,
            )
            precheck_message = apply_shopping_precheck(checkout_event)
            if precheck_message is not None:
                print(precheck_message)
                continue

            results = [
                (policy_file, decision_for(interventions[policy_file], checkout_event) == "Allow")
                for policy_file in [
                    "session_login.dw",
                    "tool_sequence.dw",
                    "approval_gate.dw",
                    "item_risk_guardrail.dw",
                    "daily_budget.dw",
                    "daily_order_quota.dw",
                ]
            ]
            print_checkout_summary(results)
            if all(allowed for _, allowed in results):
                print(checkout_cart(user, session_id))
            continue

        print(f"unknown command: {prompt}")
