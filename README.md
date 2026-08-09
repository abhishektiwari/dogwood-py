# Dogwood Policy Python SDK

Python SDK and PyO3 binding for the [Dogwood](https://github.com/dogwood-policy/dogwood) policy language. Dogwood is a policy language for fine-grained authorization decisions that depend on history or patterns of events over time - not just a single request. It adds temporal conditions (since, formerly, once, aggregations) and information providers (computed guardrail facts) on top of [Cedar](https://www.cedarpolicy.com/) policy syntax, then lowers everything back to Cedar for evaluation. Existing Cedar policies stay valid as-is. For information, **[read the Dogwood documentation](https://dogwood-policy.github.io/dogwood/index.html)**.

> ⚠️⚠️⚠️ Current Dogwood reference interpreter is not intended for production use;
therefore, this Python SDK and PyO3 binding is experimental in nature.


![GitHub Release](https://img.shields.io/github/v/release/abhishektiwari/dogwood-py)
![GitHub Actions Test Workflow Status](https://img.shields.io/github/actions/workflow/status/abhishektiwari/dogwood-py/test.yml?label=tests)
![PyPI - Version](https://img.shields.io/pypi/v/dogwood-py)
![Python Wheels](https://img.shields.io/pypi/wheel/dogwood-py)
![Python Versions](https://img.shields.io/pypi/pyversions/dogwood-py?logo=python&logoColor=white)
![GitHub last commit](https://img.shields.io/github/last-commit/abhishektiwari/dogwood-py)
![PyPI - Status](https://img.shields.io/pypi/status/dogwood-py)
![Conda Version](https://img.shields.io/conda/v/dogwood-py/dogwood-py)
![License](https://img.shields.io/github/license/abhishektiwari/dogwood-py)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/abhishektiwari/dogwood-py/total?label=GitHub%20Downloads)
![PyPI Downloads](https://img.shields.io/pepy/dt/dogwood-py?label=PyPI%20Downloads)

The public API is modeled after the Rust `dogwood-language` lifecycle:

1. Build a `ServiceSchema` and `PolicySchema`.
2. Parse and lower policy source into a `LoweredPolicySet`.
3. Validate it.
4. Feed `Event` values to a stateful `Authorizer`.

This package uses PyO3/maturin to bind the Rust `dogwood-language` reference
for schema-backed lowering, validation, and trace replay. The Python SDK also
keeps a temporary pure-Python fallback only for source-tree examples that omit
a full Cedar action schema. Schema-backed workflows require the native
extension.

dogwood-py also provides optional Strands Agents support. Dogwood policies can
be attached as Strands interventions so tool calls are checked before execution,
with typed outcomes such as proceed, deny, guide, confirm, and transform.

## Install

Install the latest released package from PyPI:

```bash
pip install dogwood-py
```

To install the optional example dependencies:

```bash
pip install "dogwood-py[examples]"
```

To install the optional Strands Agents integration:

```bash
pip install "dogwood-py[strands]"
```

The package installs as `dogwood`:

```python
from dogwood import native

assert native.available()
```


## Native vs. Non-Native Execution

This package has two execution paths.

**Native path**
The native extension imports as `dogwood._dogwood_native`; convenience wrappers
live in `dogwood.native`. The native path is the PyO3 extension built by maturin. It calls the Rust
`dogwood-language` reference implementation.

Used for:

- schema-backed policy lowering
- schema-backed validation
- schema-backed trace replay
- augmented Cedar schema export

This is the path to use for compatibility with the Rust reference. It requires
a real Cedar action schema.

You can check whether it is available:

```python
from dogwood import native

assert native.available()
```

For repeated decisions, use a persistent native authorizer so policy lowering
happens once:

```python
from dogwood import native

authorizer = native.NativeAuthorizer(policy_source, cedar_schema_source)

decision = authorizer.authorize_request(
    "Drupe::Action::SellShares",
    'Drupe::OAuthUser::"alice"',
    'Drupe::Gateway::"trading"',
    {"shares": 25, "stock": "AMZN"},
)

assert decision == "Allow"
```

**Non-native fallback**

The fallback path is pure Python. It exists only so SDK examples can run
without a full Cedar schema while the native API surface is still being built
out.

It supports only a small subset:

- basic `permit` / `forbid`
- `when` / `unless` checks over `context.*`
- simple trace parsing
- simple `formerly within` temporal checks

It is not a replacement for the Rust reference implementation.

The SDK requires native behavior when a non-empty `PolicySchema` is supplied.
It will raise a clear error if the native extension is missing. If the schema is
empty, examples may still use the Python fallback.

## Event Schema

Dogwood has two schema layers:

- The **policy/action schema** is the Cedar `.cedarschema` file. It defines
  entities, actions, and request context types such as
  `context.input.amount`.
- The **event schema** tells Dogwood how actions become historical events:
  which event kinds exist (`request`, `response`, `error`), which fields are
  recorded in the temporal history, and which event kinds produce authorization
  decisions.

If no event schema is supplied, Dogwood uses its default event schema. Under
that default, `request` events are decision points, and the event history
records request `input` fields plus reserved fields like `callerPrincipal`,
`callerResource`, and `requestId`. That is why a temporal policy can ask about
past events such as:

```text
Drupe::Action::"Transfer"::request{ input.user: context.input.user }
```

In other words, the Cedar schema says what a `Transfer` request looks like;
the event schema says that `Transfer::request` is both authorizable and stored
in history for later temporal checks.

To supply an explicit `.dwschema`:

```python
from pathlib import Path
from dogwood import LoweredPolicySet, ServiceSchema

service = ServiceSchema(event_schema=Path("event.dwschema").read_text())
policies = LoweredPolicySet.from_str(policy, service, policy_schema)
```

## Python API

```python
from dogwood import Authorizer, Event, LoweredPolicySet, PolicySchema, ServiceSchema

policy = '''
@id("sell_small_only")
permit (
    principal,
    action == Drupe::Action::"SellShares",
    resource
)
when { context.input.shares <= 50 };
'''

policies = LoweredPolicySet.from_str(policy, ServiceSchema.defaults(), PolicySchema(""))
authorizer = Authorizer(policies)

event = (
    Event.builder('Drupe::Action::"SellShares"', "request")
    .principal('Drupe::OAuthUser::"alice"')
    .resource('Drupe::Gateway::"gw1"')
    .field("input", "shares", 50)
    .request_context("input", "shares", 50)
    .build()
)

assert authorizer.is_authorized(event).allowed()
```

There is also a runnable example:

```bash
make example
```

## FastAPI Native Example

The FastAPI example uses the native binding and a real Cedar schema. It loads
its own `examples/fastapi_simple/policy.dw` and
`examples/fastapi_simple/schema.cedarschema` plus
`examples/fastapi_simple/event.dwschema`, creates a persistent
`native.NativeAuthorizer`, and exposes an authorization endpoint.

The policy enforces a `$50` daily transfer limit per user. Three `$20`
transfers by the same user produce:

```text
Allow, Allow, Deny
```

Run it:

```bash
make develop
make examples-deps
make fastapi-example
```

First transfer:

```bash
curl -s http://127.0.0.1:8000/authorize \
  -H 'content-type: application/json' \
  -d '{"user":"alice","amount":20}'
```

Expected response:

```json
{"decision":"Allow","allowed":true,"daily_limit":50}
```

Second transfer:

```bash
curl -s http://127.0.0.1:8000/authorize \
  -H 'content-type: application/json' \
  -d '{"user":"alice","amount":20}'
```

Expected response:

```json
{"decision":"Allow","allowed":true,"daily_limit":50}
```

Third transfer:

```bash
curl -s http://127.0.0.1:8000/authorize \
  -H 'content-type: application/json' \
  -d '{"user":"alice","amount":20}'
```

Expected response:

```json
{"decision":"Deny","allowed":false,"daily_limit":50}
```

Dogwood authorizers are stateful. The example keeps one shared native
authorizer and protects it with a lock. For high-throughput services, use a
pool or request-partitioned authorizers based on your temporal semantics.

The same FastAPI app also includes a quota-based rate limit endpoint:

```bash
curl -s http://127.0.0.1:8000/authorize/quota \
  -H 'content-type: application/json' \
  -d '{"user":"carol","amount":1}'
```

That endpoint uses `examples/fastapi_simple/quota_policy.dw`, which permits fewer
than three transfers by the same user within one hour. For one user, the first
two requests are allowed and the third is denied.

## CLI

```bash
dogwood-py validate policy.dw --policy-schema schema.cedarschema
dogwood-py replay policy.dw --policy-schema schema.cedarschema --trace trace.log
dogwood-py lower policy.dw --policy-schema schema.cedarschema
dogwood-py replay policy.dw --policy-schema schema.cedarschema --event-schema event.dwschema --trace trace.log
```

When using the local virtualenv directly:

```bash
.venv/bin/dogwood-py validate policy.dw --policy-schema schema.cedarschema
```

Run the checked-in CLI example:

```bash
make cli-example
```

Equivalent command:

```bash
.venv/bin/dogwood-py replay examples/cli/policy.dw \
  --policy-schema examples/cli/schema.cedarschema \
  --trace examples/cli/trace.log
```

Expected output:

```text
@0 (time point 0): true
@1 (time point 1): false
```

## Make Targets

- `make setup` creates `.venv` and installs development tools.
- `make activate` prints the command to activate `.venv`.
- `make deactivate` prints the command to deactivate `.venv`.
- `make develop` builds and installs the PyO3 extension in editable mode.
- `make examples-deps` installs optional dependencies used by examples.
- `make test` runs the Python test suite.
- `make perf-test` runs the opt-in native-vs-Python replay performance check.
- `make example` runs `examples/api_usage.py`.
- `make cli-example` runs the `dogwood-py replay` example.
- `make fastapi-example` starts the native-backed FastAPI server.
- `make strands-shopping-agent` runs the Strands shopping agent example.
- `make docs` builds Sphinx HTML documentation in `docs/build/html`.
- `make docs-watch` rebuilds and serves docs at `http://127.0.0.1:8001`.
- `make build` builds a wheel with maturin.
- `make clean` removes generated caches and Rust build output.

The performance test is a coarse regression guard, not a precise benchmark. It
uses `DOGWOOD_PERF_TESTS=1`, prints native and pure-Python replay timings, and
asserts the Rust-backed end-to-end path is not catastrophically slower than the
fallback on the same generated trace. Tune the ceiling with
`DOGWOOD_NATIVE_MAX_RATIO` when needed.

Latest local performance check:

```text
native replay: 0.4793s
python fallback replay: 0.0708s
ratio native/python: 6.77

persistent native authorizer: 0.4424s
python fallback authorizer: 0.0147s
ratio native/python: 30.14
```

This result does not mean the reference Rust implementation is slower in general. The
test compares the full native Dogwood path, including real schema-backed Rust
lowering/replay semantics, against the intentionally minimal Python fallback.
The value of the test is detecting large accidental regressions in the binding
path, not benchmarking the Rust engine in isolation.

The persistent native authorizer avoids repeated policy lowering, but each
request still crosses the Python/Rust boundary, converts Python input into
Dogwood values, and runs the full Cedar-backed decision path. The fallback
remains much faster for this tiny policy because it evaluates only a narrow
regex-parsed subset with no real Cedar schema semantics.

## Current Scope

Rust-backed operations cover schema-backed lowering, validation, and trace
replay. The Python fallback is temporary and schema-less only. The intended end
state is to remove it once the Rust-backed SDK objects cover the same ergonomic
surface.
