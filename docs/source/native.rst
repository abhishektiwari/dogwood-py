Native Rust Binding
===================

.. meta::
   :description: Use the dogwood-py native Rust binding powered by PyO3 and maturin for schema-backed Dogwood policy lowering, validation, trace replay, and authorization.
   :keywords: dogwood-py native, Dogwood Rust binding, PyO3, maturin, Cedar policy validation, temporal authorization

This package has two execution paths.

Native path
-----------

The native extension imports as :mod:`dogwood._dogwood_native`; convenience
wrappers live in :mod:`dogwood.native`. The native path is the PyO3 extension
built by maturin. It calls the Rust ``dogwood-language`` reference
implementation.

Used for:

* schema-backed policy lowering
* schema-backed validation
* schema-backed trace replay
* augmented Cedar schema export

This is the path to use for compatibility with the Rust reference. It requires
a real Cedar action schema.

You can check whether it is available:

.. code-block:: python

   from dogwood import native

   assert native.available()

For repeated decisions, use a persistent native authorizer so policy lowering
happens once:

.. code-block:: python

   from dogwood import native

   authorizer = native.NativeAuthorizer(policy_source, cedar_schema_source)

   decision = authorizer.authorize_request(
       "Agent::Action::SellShares",
       'Agent::OAuthUser::"alice"',
       'Agent::Gateway::"trading"',
       {"shares": 25, "stock": "AMZN"},
   )

   assert decision == "Allow"

SDK enforcement modes
---------------------

Dogwood's Rust core evaluates policy and returns a policy decision. ``dogwood-py``
adds SDK-level rollout behavior with :class:`dogwood.PolicyEnforcer`:

* ``mode="enforce"`` treats Dogwood denials as effective denials. This is the
  default.
* ``mode="log_only"`` evaluates the policy but lets the operation continue,
  while reporting that Dogwood would have denied it.

.. code-block:: python

   from dogwood import PolicyEnforcer, native

   authorizer = native.NativeAuthorizer(policy_source, cedar_schema_source)
   enforcer = PolicyEnforcer(authorizer, mode="log_only")

   result = enforcer.authorize_request(
       "Agent::Action::SellShares",
       'Agent::OAuthUser::"alice"',
       'Agent::Gateway::"trading"',
       {"shares": 75, "stock": "AMZN"},
   )

   assert result.allowed is True
   assert result.would_have_denied is True
   assert result.decision == "Deny"

Use ``log_only`` when introducing or tuning a policy. Switch to ``enforce``
when a denied Dogwood decision should block the protected operation.

Non-native fallback
-------------------

The fallback path is pure Python. It exists only so SDK examples can run
without a full Cedar schema while the native API surface is still being built
out.

It supports only a small subset:

* basic ``permit`` / ``forbid``
* ``when`` / ``unless`` checks over ``context.*``
* simple trace parsing
* simple ``formerly within`` temporal checks

It is not a replacement for the Rust reference implementation.

The SDK requires native behavior when a non-empty ``PolicySchema`` is supplied.
It will raise a clear error if the native extension is missing. If the schema is
empty, examples may still use the Python fallback.

See :doc:`getting-started` for the Python workflow, :doc:`api` for generated
API reference, and :doc:`examples/index` for runnable CLI, FastAPI, and Strands
examples.
