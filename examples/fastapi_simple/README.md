# FastAPI Native Dogwood Example

This example uses the PyO3 native binding with a real Cedar schema.

Amount-limit policy: `policy.dw`

Quota policy: `quota_policy.dw`

Schema: `schema.cedarschema`

The policy enforces a `$50` daily transfer limit per user. Because Dogwood's
authorizer is stateful, each accepted `Transfer::request` becomes part of the
event history. Three `$20` transfers by the same user produce:

```text
Allow, Allow, Deny
```

Run from the repository root:

```bash
make develop
make examples-deps
make fastapi-example
```

Then send three requests:

```bash
curl -s http://127.0.0.1:8000/authorize \
  -H 'content-type: application/json' \
  -d '{"user":"alice","amount":20}'
```

The third request is denied because the daily total would be `$60`, exceeding
the `$50` limit.

The example also exposes a quota-based rate limit:

```bash
curl -s http://127.0.0.1:8000/authorize/quota \
  -H 'content-type: application/json' \
  -d '{"user":"alice","amount":1}'
```

The quota policy permits fewer than three `Transfer::request` events by the
same user within one hour, so the first two requests are allowed and the third
is denied.
