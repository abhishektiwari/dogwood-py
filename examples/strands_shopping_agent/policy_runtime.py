from __future__ import annotations

import hashlib
import re
from types import SimpleNamespace
from typing import Any

from dogwood.integrations.strands import DogwoodIntervention, guide, proceed, transform

from examples.strands_shopping_agent.cart_store import CART_ITEMS, shopping_cart_id
from examples.strands_shopping_agent.config import (
    AGENT_POLICIES_DIR,
    PRODUCTS,
    SHOPPING_EVENT_SCHEMA_SOURCE,
    SHOPPING_ACTION,
    RISK_MAPPING,
    SHOPPING_SCHEMA_SOURCE,
)

POLICY_FILES = [
    "session_access.dw",
    "session_login.dw",
    "tool_sequence.dw",
    "approval_gate.dw",
    "item_risk_guardrail.dw",
    "daily_budget.dw",
    "daily_order_quota.dw",
]

try:  # pragma: no cover - exercised only when Strands is installed
    from strands.interventions import InterventionHandler as _StrandsInterventionHandler
except ImportError:  # pragma: no cover - local console/tests use fallback behavior
    _StrandsInterventionHandler = object


def policy_hint(policy_file: str) -> str:
    policy_source = (AGENT_POLICIES_DIR / policy_file).read_text()
    match = re.search(r'@hint\s*\(\s*"((?:[^"\\]|\\.)*)"\s*\)', policy_source)
    if match is None:
        return "see policy for required preconditions"
    return bytes(match.group(1), "utf-8").decode("unicode_escape")


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


def next_tool_sequence(tool_use_counts: dict[str, int], tool_name: str) -> int:
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
            "toolUseId": derive_tool_use_id(user, session_id, cart_id, tool_name, sequence),
        },
        invocation_state={
            "principal": f'Agent::OAuthUser::"{user}"',
            "resource": 'Agent::Gateway::"shopping-agent"',
            "session_id": session_id,
        },
    )


def policy_intervention(policy_file: str, *, confirm_when: bool | str = False) -> DogwoodIntervention:
    return DogwoodIntervention(
        policy_source=(AGENT_POLICIES_DIR / policy_file).read_text(),
        policy_schema_source=SHOPPING_SCHEMA_SOURCE,
        event_schema_source=SHOPPING_EVENT_SCHEMA_SOURCE,
        action=SHOPPING_ACTION,
        confirm_when=confirm_when,
    )


def policy_interventions() -> dict[str, DogwoodIntervention]:
    return {policy_file: policy_intervention(policy_file) for policy_file in POLICY_FILES}


class ShoppingToolPrecheck(_StrandsInterventionHandler):
    name = "shopping-tool-precheck"

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        return shopping_tool_precheck(event)


def shopping_interventions() -> list[Any]:
    return [
        ShoppingToolPrecheck(),
        *[
            DogwoodIntervention(
                policy_source=(AGENT_POLICIES_DIR / policy_file).read_text(),
                policy_schema_source=SHOPPING_SCHEMA_SOURCE,
                event_schema_source=SHOPPING_EVENT_SCHEMA_SOURCE,
                action=SHOPPING_ACTION,
                confirm_when=(
                    "Approve this high-risk item?"
                    if policy_file == "item_risk_guardrail.dw"
                    else False
                ),
            )
            for policy_file in POLICY_FILES
        ],
    ]


def shopping_tool_precheck(event: SimpleNamespace) -> Any:
    normalized = shopping_tool_transform(event)
    if normalized is not None:
        return transform(normalized)

    feedback = shopping_tool_guidance(event)
    if feedback is not None:
        return guide(feedback)

    return proceed()


def shopping_tool_transform(event: SimpleNamespace) -> Any | None:
    tool_use = _tool_use(event)
    if tool_use is None:
        return None

    tool_input = _tool_input(tool_use)
    if not isinstance(tool_input, dict):
        return None

    updates: dict[str, Any] = {}

    item_id = tool_input.get("item_id")
    if isinstance(item_id, str):
        normalized_item = item_id.strip().lower().replace(" ", "-").replace("_", "-")
        if normalized_item != item_id:
            updates["item_id"] = normalized_item

    if "quantity" in tool_input and not isinstance(tool_input["quantity"], int):
        try:
            updates["quantity"] = int(tool_input["quantity"])
        except (TypeError, ValueError):
            pass

    tool_name = _tool_name(tool_use)
    if tool_name in {"add_to_cart", "remove_from_cart", "checkout_cart"} and not tool_input.get("cart_id"):
        user = str(tool_input.get("user", ""))
        session_id = str(tool_input.get("session_id", ""))
        if user and session_id:
            updates["cart_id"] = shopping_cart_id(user, session_id)

    if not updates:
        return None

    def apply(event_to_update: Any) -> None:
        target_tool_use = _tool_use(event_to_update)
        if target_tool_use is None:
            return
        target_input = _tool_input(target_tool_use)
        if isinstance(target_input, dict):
            target_input.update(updates)

    return apply


def shopping_tool_guidance(event: SimpleNamespace) -> str | None:
    tool_use = _tool_use(event)
    if tool_use is None:
        return "tool call missing tool_use"

    tool_name = _tool_name(tool_use)
    tool_input = _tool_input(tool_use)

    if not isinstance(tool_input, dict):
        return "tool call input must be an object"

    if tool_name in {"add_to_cart", "remove_from_cart"}:
        item_id = str(tool_input.get("item_id", ""))
        if item_id not in PRODUCTS:
            return f"Choose one of these product ids: {', '.join(sorted(PRODUCTS))}"
        try:
            quantity = int(tool_input.get("quantity", 1))
        except (TypeError, ValueError):
            return "Use a positive integer quantity."
        if quantity < 1:
            return "Use a positive integer quantity."

    if tool_name == "checkout_cart":
        user = str(tool_input.get("user", ""))
        session_id = str(tool_input.get("session_id", ""))
        cart_id = str(tool_input.get("cart_id") or shopping_cart_id(user, session_id))
        if not user:
            return "checkout missing user"
        if not session_id:
            return "checkout missing session_id"
        if not CART_ITEMS.get(cart_id):
            return "The cart is empty. Add an item before checkout."

    return None


def apply_shopping_precheck(event: SimpleNamespace) -> str | None:
    for _ in range(2):
        decision = shopping_tool_precheck(event)
        decision_name = decision.__class__.__name__
        if decision_name.endswith("Proceed"):
            return None
        if decision_name.endswith("Transform"):
            apply = getattr(decision, "apply", None)
            if callable(apply):
                apply(event)
                continue
            return "tool input transform could not be applied"
        if decision_name.endswith("Guide"):
            return str(getattr(decision, "feedback", "tool call needs correction"))
        if decision_name.endswith("Deny"):
            return str(getattr(decision, "reason", "tool call denied"))
        return "tool call needs correction"
    return "tool input normalized; retry the command"


def _tool_use(event: Any) -> Any | None:
    return getattr(event, "tool_use", None)


def _tool_name(tool_use: Any) -> str:
    if isinstance(tool_use, dict):
        return str(tool_use.get("name", ""))
    return str(getattr(tool_use, "name", ""))


def _tool_input(tool_use: Any) -> Any:
    if isinstance(tool_use, dict):
        return tool_use.get("input", {})
    return getattr(tool_use, "input", {})


def decision_for(intervention: DogwoodIntervention, event: SimpleNamespace) -> str:
    decision = intervention.before_tool_call(event)
    decision_name = decision.__class__.__name__
    if decision_name.endswith("Proceed"):
        return "Allow"
    if decision_name.endswith("Confirm"):
        return "Confirm"
    return "Deny"


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
