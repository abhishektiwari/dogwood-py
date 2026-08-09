# Shopping Agent Policies

Framework-neutral Dogwood policies for a shopping agent. These files model
agent tool calls as `Drupe::Action::"CallTool"` request events with a nested
tool input payload:

```json
{
  "tool": "checkout_cart",
  "input": {
    "user": "alice",
    "session_id": "session-1",
    "cart_id": "cart-1",
    "item_id": "iphone17",
    "category": "high-end-smartphone",
    "amount": 1299,
    "quantity": 1,
    "risk": 100,
    "status": "requested"
  },
  "toolUseId": "tool-use-1"
}
```

The shape matches the default `dogwood-py` Strands adapter, but the policy
files are not Strands-specific and can be reused by future LangChain, CrewAI,
or other agent framework adapters.

## Policies

| Policy | Agent behavior | Temporal condition | Example outcome |
| --- | --- | --- | --- |
| `daily_budget.dw` | Limits `checkout_cart` spending. | Sum prior same-user checkout amounts within 1 day and allow only while total is `<= 50`. | `$20`, `$20`, `$20` -> Allow, Allow, Deny. |
| `daily_order_quota.dw` | Limits order frequency. | Count prior same-user `checkout_cart` calls within 1 day and allow fewer than 3. | First two checkouts allow; third denies. |
| `approval_gate.dw` | Requires explicit approval before `checkout_cart`. | Same user and cart must have an `approve_checkout` event with `status == "approved"` within 1 hour. | Checkout before approval denies; checkout after approval allows. |
| `item_risk_guardrail.dw` | Requires step-up user approval for risky items before add or checkout. | Agent/framework enriches input from `products.json`, then maps product category to `risk` through `risk-mapping.json`; `add_to_cart` and `checkout_cart` are allowed when `risk <= 50` or after a recent `approve_step_up` event for the same user/cart/item. | Book add/checkout allows; iPhone 17 add denies until step-up approval, then allows. |
| `session_access.dw` | Enforces grant/revoke session access. | Tool calls require a same-user/session `grant_session` within 1 hour with no later `revoke_session`. | Search before grant denies; after grant allows; after revoke denies. |
| `tool_sequence.dw` | Requires cart context before purchase. | `checkout_cart` requires a same-user/cart `add_to_cart` for the same item within 1 hour. | Checkout before add-to-cart denies; checkout after add-to-cart allows. |
| `session_login.dw` | Requires an authenticated agent session. | Tool calls require a same-user/session `login` within 1 hour. | Search before login denies; after login allows. |

These files intentionally contain only policies and schema. The Strands example
in `examples/strands_shopping_agent` loads and executes them with
`DogwoodPlugin`.
