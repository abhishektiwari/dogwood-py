from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dogwood.integrations.strands import DogwoodIntervention

EXAMPLE_DIR = Path(__file__).parent
AGENT_POLICIES_DIR = EXAMPLE_DIR.parent / "shopping_agent_policies"
SHOPPING_SCHEMA_SOURCE = (AGENT_POLICIES_DIR / "schema.cedarschema").read_text()
RISK_MAPPING = json.loads((AGENT_POLICIES_DIR / "risk-mapping.json").read_text())
PRODUCTS = json.loads((AGENT_POLICIES_DIR / "products.json").read_text())
CART_ITEMS: dict[str, dict[str, int]] = {}

try:
    from strands import Agent, tool
except ImportError:  # pragma: no cover - depends on optional package
    Agent = None
    tool = None


def shopping_cart_id(user: str, session_id: str) -> str:
    return f"cart-{user}-{session_id}"


def policy_hint(policy_file: str) -> str:
    policy_source = (AGENT_POLICIES_DIR / policy_file).read_text()
    match = re.search(r'@hint\s*\(\s*"((?:[^"\\]|\\.)*)"\s*\)', policy_source)
    if match is None:
        return "see policy for required preconditions"
    return bytes(match.group(1), "utf-8").decode("unicode_escape")


def describe_cart(cart_id: str, *, include_cart_id: bool = True) -> str:
    items = CART_ITEMS.get(cart_id, {})
    if not items:
        return f"cart_id={cart_id}\nitems: empty" if include_cart_id else "items: empty"

    lines = [f"cart_id={cart_id}", "items:"] if include_cart_id else ["items:"]
    total = 0
    for item_id, quantity in sorted(items.items()):
        product = PRODUCTS[item_id]
        price = int(product["price"])
        subtotal = price * quantity
        total += subtotal
        lines.append(f"  {item_id} x {quantity} @ ${price} = ${subtotal}")
    lines.append(f"total=${total}")
    return "\n".join(lines)


def add_cart_item(cart_id: str, item_id: str, quantity: int) -> None:
    CART_ITEMS.setdefault(cart_id, {})
    CART_ITEMS[cart_id][item_id] = CART_ITEMS[cart_id].get(item_id, 0) + quantity


def remove_cart_item(cart_id: str, item_id: str, quantity: int) -> None:
    items = CART_ITEMS.setdefault(cart_id, {})
    if item_id not in items:
        return
    remaining = items[item_id] - quantity
    if remaining > 0:
        items[item_id] = remaining
    else:
        del items[item_id]


def checkout_session_cart(user: str, session_id: str) -> str:
    cart_id = shopping_cart_id(user, session_id)
    items = CART_ITEMS.get(cart_id, {})
    if not items:
        return f"order-{cart_id}\nitems: empty"

    order_lines = [f"order-{cart_id}", "items:"]
    total = 0
    for item_id, quantity in sorted(items.items()):
        product = PRODUCTS[item_id]
        price = int(product["price"])
        subtotal = price * quantity
        total += subtotal
        order_lines.append(f"  {item_id} x {quantity} @ ${price} = ${subtotal}")
    order_lines.append(f"total=${total}")
    CART_ITEMS[cart_id] = {}
    return "\n".join(order_lines)


def cart_policy_context(cart_id: str, fallback_item_id: str) -> dict[str, int | str]:
    items = CART_ITEMS.get(cart_id, {})
    if not items:
        product = PRODUCTS[fallback_item_id]
        category = str(product["category"])
        return {
            "item_id": fallback_item_id,
            "amount": int(product["price"]),
            "quantity": 1,
            "risk": int(RISK_MAPPING.get(category, 100)),
        }

    amount = 0
    quantity = 0
    highest_risk = -1
    highest_risk_item = fallback_item_id
    for item_id, item_quantity in items.items():
        product = PRODUCTS[item_id]
        category = str(product["category"])
        risk = int(RISK_MAPPING.get(category, 100))
        amount += int(product["price"]) * item_quantity
        quantity += item_quantity
        if risk > highest_risk:
            highest_risk = risk
            highest_risk_item = item_id

    return {
        "item_id": highest_risk_item,
        "amount": amount,
        "quantity": quantity,
        "risk": highest_risk,
    }


if tool is not None:

    @tool
    def list_products() -> str:
        return ", ".join(sorted(PRODUCTS))

    @tool
    def get_shopping_cart(user: str, session_id: str) -> str:
        return describe_cart(shopping_cart_id(user, session_id))

    @tool
    def add_to_cart(cart_id: str, item_id: str, quantity: int) -> str:
        add_cart_item(cart_id, item_id, quantity)
        return f"added {quantity} x {item_id} to {cart_id}"

    @tool
    def remove_from_cart(cart_id: str, item_id: str, quantity: int) -> str:
        remove_cart_item(cart_id, item_id, quantity)
        return f"removed {quantity} x {item_id} from {cart_id}"

    @tool
    def checkout_cart(user: str, session_id: str) -> str:
        return checkout_session_cart(user, session_id)

else:

    def list_products() -> str:
        return ", ".join(sorted(PRODUCTS))

    def get_shopping_cart(user: str, session_id: str) -> str:
        return describe_cart(shopping_cart_id(user, session_id))

    def add_to_cart(cart_id: str, item_id: str, quantity: int) -> str:
        add_cart_item(cart_id, item_id, quantity)
        return f"added {quantity} x {item_id} to {cart_id}"

    def remove_from_cart(cart_id: str, item_id: str, quantity: int) -> str:
        remove_cart_item(cart_id, item_id, quantity)
        return f"removed {quantity} x {item_id} from {cart_id}"

    def checkout_cart(user: str, session_id: str) -> str:
        return checkout_session_cart(user, session_id)


def build_agent() -> Any:
    if Agent is None:
        return None

    return Agent(
        tools=[list_products, get_shopping_cart, add_to_cart, remove_from_cart, checkout_cart],
        interventions=[
            DogwoodIntervention(
                policy_source=(AGENT_POLICIES_DIR / policy_file).read_text(),
                policy_schema_source=SHOPPING_SCHEMA_SOURCE,
                confirm_when=(
                    "Approve this high-risk item?"
                    if policy_file == "item_risk_guardrail.dw"
                    else False
                ),
            )
            for policy_file in [
                "session_access.dw",
                "session_login.dw",
                "tool_sequence.dw",
                "approval_gate.dw",
                "item_risk_guardrail.dw",
                "daily_budget.dw",
                "daily_order_quota.dw",
            ]
        ],
    )


def demo_session_id(user: str) -> str:
    return f"demo-session-{user}"


def derive_tool_use_id(
    user: str,
    session_id: str,
    cart_id: str,
    tool_name: str,
    sequence: int = 1,
) -> str:
    seed = f"{user}:{session_id}:{cart_id}:{tool_name}:{sequence}".encode()
    digits = str(int(hashlib.sha256(seed).hexdigest(), 16))[:12]
    return f"tooluse_{tool_name}_{digits}"


def next_tool_sequence(
    tool_use_counts: dict[str, int],
    tool_name: str,
) -> int:
    tool_use_counts[tool_name] = tool_use_counts.get(tool_name, 0) + 1
    return tool_use_counts[tool_name]


def build_shopping_tool_event(
    tool_name: str,
    *,
    user: str = "alice",
    session_id: str = "session-1",
    cart_id: str = "cart-1",
    item_id: str = "developer-laptop",
    amount: int | None = None,
    quantity: int = 1,
    risk: int | None = None,
    status: str = "requested",
    sequence: int = 1,
) -> SimpleNamespace:
    product = PRODUCTS.get(item_id, {"category": "unknown", "price": 0})
    category = str(product["category"])
    risk_score = RISK_MAPPING.get(category, 100) if risk is None else risk
    amount_value = int(product["price"]) * quantity if amount is None else amount
    event_tool_use_id = derive_tool_use_id(
        user,
        session_id,
        cart_id,
        tool_name,
        sequence,
    )
    return SimpleNamespace(
        tool_use={
            "name": tool_name,
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
            "toolUseId": event_tool_use_id,
        },
        invocation_state={
            "principal": f'Drupe::OAuthUser::"{user}"',
            "resource": 'Drupe::Gateway::"shopping-agent"',
            "session_id": session_id,
        },
    )


def decision_for(intervention: DogwoodIntervention, event: SimpleNamespace) -> str:
    decision = intervention.before_tool_call(event)
    decision_name = decision.__class__.__name__
    if decision_name.endswith("Proceed"):
        return "Allow"
    if decision_name.endswith("Confirm"):
        return "Confirm"
    return "Deny"


def policy_intervention(policy_file: str, *, confirm_when: bool | str = False) -> DogwoodIntervention:
    return DogwoodIntervention(
        policy_source=(AGENT_POLICIES_DIR / policy_file).read_text(),
        policy_schema_source=SHOPPING_SCHEMA_SOURCE,
        confirm_when=confirm_when,
    )


def policy_interventions() -> dict[str, DogwoodIntervention]:
    return {
        policy_file: policy_intervention(policy_file)
        for policy_file in [
            "approval_gate.dw",
            "daily_budget.dw",
            "daily_order_quota.dw",
            "item_risk_guardrail.dw",
            "session_access.dw",
            "session_login.dw",
            "tool_sequence.dw",
        ]
    }


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Strands shopping-agent policy demo.")
    parser.add_argument("--user", required=True, help="Shopping user name/principal id.")
    parser.add_argument(
        "--resume-session",
        help="Existing Strands session id to resume. Defaults to a generated demo session.",
    )
    parser.add_argument(
        "--item-id",
        default="developer-laptop",
        choices=sorted(PRODUCTS),
        help="Product id from examples/shopping_agent_policies/products.json.",
    )
    parser.add_argument(
        "--scripted",
        action="store_true",
        help="Run the deterministic policy walkthrough instead of the interactive console.",
    )
    return parser.parse_args()


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


def run_tool_with_policy(
    interventions: dict[str, DogwoodIntervention],
    policy_file: str,
    tool_name: str,
    *,
    user: str,
    session_id: str,
    cart_id: str,
    item_id: str,
    amount: int | None = None,
    quantity: int = 1,
    risk: int | None = None,
    status: str = "requested",
    sequence: int = 1,
) -> bool:
    event = build_shopping_tool_event(
        tool_name,
        user=user,
        session_id=session_id,
        cart_id=cart_id,
        item_id=item_id,
        amount=amount,
        quantity=quantity,
        risk=risk,
        status=status,
        sequence=sequence,
    )
    decision = decision_for(interventions[policy_file], event)
    print(f"{policy_file}: {decision}")
    if decision != "Allow":
        print(f"blocked: {tool_name}")
        return False
    return True


def policy_allows(
    interventions: dict[str, DogwoodIntervention],
    policy_file: str,
    tool_name: str,
    *,
    user: str,
    session_id: str,
    cart_id: str,
    item_id: str,
    amount: int | None = None,
    quantity: int = 1,
    risk: int | None = None,
    status: str = "requested",
    sequence: int = 1,
) -> bool:
    event = build_shopping_tool_event(
        tool_name,
        user=user,
        session_id=session_id,
        cart_id=cart_id,
        item_id=item_id,
        amount=amount,
        quantity=quantity,
        risk=risk,
        status=status,
        sequence=sequence,
    )
    return decision_for(interventions[policy_file], event) == "Allow"


def policy_allows_with_history(
    policy_file: str,
    history: list[SimpleNamespace],
    event: SimpleNamespace,
) -> bool:
    intervention = policy_intervention(policy_file)
    for previous_event in history:
        decision_for(intervention, previous_event)
    return decision_for(intervention, event) == "Allow"


def session_access_allows(
    interventions: dict[str, DogwoodIntervention],
    tool_name: str,
    *,
    user: str,
    session_id: str,
    cart_id: str,
    item_id: str,
    quantity: int = 1,
    sequence: int = 1,
) -> bool:
    return policy_allows(
        interventions,
        "session_access.dw",
        tool_name,
        user=user,
        session_id=session_id,
        cart_id=cart_id,
        item_id=item_id,
        quantity=quantity,
        sequence=sequence,
    )


def print_checkout_summary(results: list[tuple[str, bool]]) -> None:
    failed = [policy_file for policy_file, allowed in results if not allowed]
    if not failed:
        print("checkout policy summary: all controls passed. checkout completed successfully.")
        return

    print("checkout blocked by:")
    for policy_file in failed:
        print(f"  {policy_file}: {policy_hint(policy_file)}")


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
    successful_checkout_events: list[SimpleNamespace] = []
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
            if allowed:
                print(list_products())
            else:
                print(policy_hint("session_access.dw"))
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
            if allowed:
                print(describe_cart(cart_id, include_cart_id=False))
            else:
                print(policy_hint("session_access.dw"))
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
            access_allowed = session_access_allows(
                interventions,
                "add_to_cart",
                user=user,
                session_id=session_id,
                cart_id=cart_id,
                item_id=current_item,
                quantity=quantity,
                sequence=sequence,
            )
            if not access_allowed:
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
            if allowed:
                print(remove_from_cart(cart_id, current_item, quantity))
            else:
                print(policy_hint("session_access.dw"))
            continue

        if command == "checkout":
            if not CART_ITEMS.get(cart_id):
                print("checkout blocked: cart is empty")
                print("next step: add an item before checkout")
                continue

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
            state_policies = [
                "session_login.dw",
                "tool_sequence.dw",
                "approval_gate.dw",
                "item_risk_guardrail.dw",
            ]
            state_results = [
                (policy_file, decision_for(interventions[policy_file], checkout_event) == "Allow")
                for policy_file in state_policies
            ]
            spending_results = [
                (
                    policy_file,
                    policy_allows_with_history(
                        policy_file,
                        successful_checkout_events,
                        checkout_event,
                    ),
                )
                for policy_file in [
                    "daily_budget.dw",
                    "daily_order_quota.dw",
                ]
            ]
            results = state_results + spending_results
            print_checkout_summary(results)
            if all(allowed for _, allowed in results):
                successful_checkout_events.append(checkout_event)
                print(checkout_cart(user, session_id))
            continue

        print(f"unknown command: {prompt}")


def main() -> None:
    args = parse_args()
    session_id = args.resume_session or demo_session_id(args.user)
    cart_id = shopping_cart_id(args.user, session_id)

    agent = build_agent()
    if agent is None:
        print("Strands is not installed; running the Dogwood policy check directly.")
    else:
        print(f"Created Strands agent: {agent.__class__.__name__}")

    print(f"user={args.user}")
    print(f"session_id={session_id}")
    print(f"cart_id={cart_id}")

    if args.scripted:
        check_shopping_agent_policies(args.user, session_id, cart_id, args.item_id)
        return

    run_interactive_console(args.user, session_id, cart_id, args.item_id)


if __name__ == "__main__":
    main()
