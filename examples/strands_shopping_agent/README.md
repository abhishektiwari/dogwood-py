# Strands Shopping Agent Example

This example wires Strands-style agent tool calls through Dogwood
interventions.

The example loads shared temporal shopping policies from
`examples/shopping_agent_policies`:

- `daily_budget.dw` enforces a `$50` daily shopping budget per user.
- `daily_order_quota.dw` permits fewer than three orders per user within one
  day.

When Strands is installed, the example attaches one `DogwoodIntervention` per
policy. Each intervention runs before tool execution and returns a typed
Strands decision such as proceed, deny, or confirm. The local console uses the
same policies directly so the example remains runnable without Strands.

Run it from the repository root:

```bash
make develop
make strands-shopping-agent ARGS="--user alice"
```

This opens an interactive console:

```text
shopping-agent>
```

Useful commands:

```text
products
cart
add clean-code-book 2
remove clean-code-book 1
checkout
```

`cart` prints the current user id, session id, cart id, and the items in the
session cart. `checkout` uses the active session cart; you do not pass a cart id
to the command.

When checkout is blocked, the console prints only the controls that failed and
the next action to take. Lifecycle commands such as `grant`, `login`,
`approve`, and `step-up` are recorded as history events for Dogwood policies.

## Recommended Flows

A normal low-risk purchase flow:

```text
grant
products
cart
add iphone17-case 1
login
approve
checkout
cart
quit
```

A high-risk purchase flow, such as `iphone17`, requires step-up user approval
before the item can be added:

```text
grant
products
add iphone17 1
step-up
add iphone17 1
cart
login
approve
checkout
cart
quit
```

This flow demonstrates layered controls. `step-up` only satisfies the
high-risk item control; it does not override the daily budget, checkout
approval, session login, or order quota policies. For example, `iphone17`
can be added after step-up approval, but checkout is still denied by
`daily_budget.dw` because the item price is `$1299` and the daily budget is
`$50`.

Command meaning:

```text
grant      # allow this user/session to use shopping tools
products   # inspect available products
add ...    # add normal items, or trigger step-up for risky ones
step-up    # user confirms a risky item
login      # session is authenticated
approve    # user approves checkout
checkout   # place the order
cart       # confirm cart is empty after checkout
```
