from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXAMPLE_DIR = Path(__file__).parent
AGENT_POLICIES_DIR = EXAMPLE_DIR.parent / "shopping_agent_policies"
SHOPPING_SCHEMA_SOURCE = (AGENT_POLICIES_DIR / "schema.cedarschema").read_text()
SHOPPING_EVENT_SCHEMA_SOURCE = (AGENT_POLICIES_DIR / "event.dwschema").read_text()
SHOPPING_TOOL_ACTION_GROUP = "Agent::Action::ShoppingTool"
SHOPPING_TOOL_ACTIONS = {
    "grant_session": "Agent::Action::GrantSession",
    "revoke_session": "Agent::Action::RevokeSession",
    "login": "Agent::Action::Login",
    "approve_checkout": "Agent::Action::ApproveCheckout",
    "approve_step_up": "Agent::Action::ApproveStepUp",
    "get_shopping_cart": "Agent::Action::GetShoppingCart",
    "list_products": "Agent::Action::ListProducts",
    "add_to_cart": "Agent::Action::AddToCart",
    "remove_from_cart": "Agent::Action::RemoveFromCart",
    "checkout_cart": "Agent::Action::CheckoutCart",
}
RISK_MAPPING = json.loads((AGENT_POLICIES_DIR / "risk-mapping.json").read_text())
PRODUCTS = json.loads((AGENT_POLICIES_DIR / "products.json").read_text())


def shopping_action(event: Any) -> str:
    tool_use = getattr(event, "tool_use", {})
    if isinstance(tool_use, dict):
        tool_name = str(tool_use.get("name", ""))
    else:
        tool_name = str(getattr(tool_use, "name", ""))
    return SHOPPING_TOOL_ACTIONS.get(tool_name, SHOPPING_TOOL_ACTION_GROUP)


SHOPPING_ACTION = shopping_action
