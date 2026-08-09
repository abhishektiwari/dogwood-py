from __future__ import annotations

from examples.strands_shopping_agent.config import PRODUCTS, RISK_MAPPING

CART_ITEMS: dict[str, dict[str, int]] = {}


def shopping_cart_id(user: str, session_id: str) -> str:
    return f"cart-{user}-{session_id}"


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

