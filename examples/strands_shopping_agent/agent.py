from __future__ import annotations

import argparse
from typing import Any

from dogwood.integrations.strands import DogwoodIntervention

from examples.strands_shopping_agent.cart_store import (
    CART_ITEMS,
    cart_policy_context,
    checkout_session_cart,
    describe_cart,
    shopping_cart_id,
)
from examples.strands_shopping_agent.config import (
    AGENT_POLICIES_DIR,
    PRODUCTS,
    SHOPPING_SCHEMA_SOURCE,
)
from examples.strands_shopping_agent.console import (
    check_shopping_agent_policies,
    run_interactive_console,
)
from examples.strands_shopping_agent.policy_runtime import (
    build_shopping_tool_event,
    next_tool_sequence,
    policy_hint,
    shopping_interventions,
)
from examples.strands_shopping_agent.tools import (
    SHOPPING_TOOLS,
    add_to_cart,
    checkout_cart,
    get_shopping_cart,
    list_products,
    remove_from_cart,
)

try:
    from strands import Agent
except ImportError:  # pragma: no cover - depends on optional package
    Agent = None


def build_agent() -> Any:
    if Agent is None:
        return None

    return Agent(
        tools=SHOPPING_TOOLS,
        interventions=shopping_interventions(),
    )


def demo_session_id(user: str) -> str:
    return f"demo-session-{user}"


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


__all__ = [
    "AGENT_POLICIES_DIR",
    "CART_ITEMS",
    "DogwoodIntervention",
    "SHOPPING_SCHEMA_SOURCE",
    "add_to_cart",
    "build_agent",
    "build_shopping_tool_event",
    "cart_policy_context",
    "checkout_cart",
    "checkout_session_cart",
    "demo_session_id",
    "describe_cart",
    "get_shopping_cart",
    "list_products",
    "main",
    "next_tool_sequence",
    "policy_hint",
    "remove_from_cart",
    "shopping_cart_id",
]


if __name__ == "__main__":
    main()
