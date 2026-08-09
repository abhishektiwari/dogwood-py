from __future__ import annotations

import json
from pathlib import Path

EXAMPLE_DIR = Path(__file__).parent
AGENT_POLICIES_DIR = EXAMPLE_DIR.parent / "shopping_agent_policies"
SHOPPING_SCHEMA_SOURCE = (AGENT_POLICIES_DIR / "schema.cedarschema").read_text()
SHOPPING_EVENT_SCHEMA_SOURCE = (AGENT_POLICIES_DIR / "event.dwschema").read_text()
RISK_MAPPING = json.loads((AGENT_POLICIES_DIR / "risk-mapping.json").read_text())
PRODUCTS = json.loads((AGENT_POLICIES_DIR / "products.json").read_text())
