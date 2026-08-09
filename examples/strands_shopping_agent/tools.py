from __future__ import annotations

from examples.strands_shopping_agent.cart_store import (
    add_cart_item,
    checkout_session_cart,
    describe_cart,
    remove_cart_item,
    shopping_cart_id,
)
from examples.strands_shopping_agent.config import PRODUCTS

try:
    from strands import tool
except ImportError:  # pragma: no cover - depends on optional package
    tool = None


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


if tool is not None:
    list_products = tool(list_products)
    get_shopping_cart = tool(get_shopping_cart)
    add_to_cart = tool(add_to_cart)
    remove_from_cart = tool(remove_from_cart)
    checkout_cart = tool(checkout_cart)

SHOPPING_TOOLS = [list_products, get_shopping_cart, add_to_cart, remove_from_cart, checkout_cart]
