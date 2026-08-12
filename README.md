# Dogwood Policy Python SDK

Python SDK and PyO3 binding for the [Dogwood](https://github.com/dogwood-policy/dogwood) policy language. Dogwood supports fine-grained authorization decisions that depend on history or patterns of events over time, then lowers policies back to [Cedar](https://www.cedarpolicy.com/) for evaluation.

For full documentation, see **[dogwood-py.abhishek-tiwari.com](https://dogwood-py.abhishek-tiwari.com/)**.

> ⚠️⚠️⚠️ Current Dogwood reference interpreter is not intended for production use;
therefore, this Python SDK and PyO3 binding is experimental in nature.

> **Note:** This is an unofficial Python SDK and port for Dogwood Policy.
> Support is provided on a best effort basis with community help.

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

## Install

```bash
pip install dogwood-py
```

Optional extras:

```bash
pip install "dogwood-py[examples]"        # FastAPI and general examples
pip install "dogwood-py[strands]"         # Strands integration and shopping-agent example
pip install "dogwood-py[examples,strands]"
```

The package installs as `dogwood`:

```python
from dogwood import native

assert native.available()
```

## What It Provides

The public API follows the Rust `dogwood-language` lifecycle:

1. Build a `ServiceSchema` and `PolicySchema`.
2. Parse and lower policy source into a `LoweredPolicySet`.
3. Validate it.
4. Feed `Event` values to a stateful `Authorizer`.

The native path uses PyO3/maturin to call the Rust Dogwood reference implementation for schema-backed lowering, validation, trace replay, augmented Cedar schema export, and authorization. A temporary pure-Python fallback remains only for limited schema-less examples.

The Python SDK includes a [`PolicyEnforcer`](https://dogwood-py.abhishek-tiwari.com/generated/dogwood.enforcement.html) wrapper with `mode="enforce"` and `mode="log_only"` for rollout and audit behavior. Dogwood still evaluates the policy; the SDK mode controls whether a denied decision blocks the operation or is reported as `would_have_denied`.

`dogwood-py` also provides optional Strands Agents support. Dogwood policies can be attached as Strands interventions so tool calls are checked before execution, with typed outcomes such as proceed, deny, guide, confirm, and transform.

Strands integrations use the same SDK-level `enforce` and `log_only` modes on top of the Rust Dogwood policy decision.

## Documentation

- [Installation](https://dogwood-py.abhishek-tiwari.com/installation.html)
- [Getting Started](https://dogwood-py.abhishek-tiwari.com/getting-started.html)
- [Native Rust Binding](https://dogwood-py.abhishek-tiwari.com/native.html)
- [Strands Agents Integration](https://dogwood-py.abhishek-tiwari.com/strands.html)
- [PolicyEnforcer API](https://dogwood-py.abhishek-tiwari.com/generated/dogwood.enforcement.html)
- [Examples](https://dogwood-py.abhishek-tiwari.com/examples/index.html)
- [API Reference](https://dogwood-py.abhishek-tiwari.com/api.html)

Dogwood language documentation is available at [dogwood-policy.github.io/dogwood](https://dogwood-policy.github.io/dogwood/index.html).

## Examples

Checked-in examples are documented at [Examples](https://dogwood-py.abhishek-tiwari.com/examples/index.html).
After installing the package and optional dependencies, run examples directly:

```bash
python -m examples.api_usage

python -m examples.cli

python -m uvicorn examples.fastapi_simple.app:app --host 127.0.0.1 --port 8000

python -m examples.strands_shopping_agent.agent --user alice
```

## Development

```bash
make setup
make develop
make test
make docs
make build
```

Useful targets:

- `make docs-ci` installs docs-only dependencies and builds Sphinx HTML docs.
- `make docs-watch` serves live-reloading docs at `http://127.0.0.1:8001`.
- `make perf-test` runs the opt-in native-vs-Python replay regression check.

The docs-only Cloudflare Pages build command is:

```bash
make docs-ci PYTHON=python
```

Build output directory:

```text
docs/build/html
```

## Current Scope

Rust-backed operations cover schema-backed lowering, validation, authorization, and trace replay. The Python fallback is temporary and schema-less only. The intended end state is to remove it once the Rust-backed SDK objects cover the same ergonomic surface.
