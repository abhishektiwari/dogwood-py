Native vs. Non-Native Execution
===============================

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
       "Drupe::Action::SellShares",
       'Drupe::OAuthUser::"alice"',
       'Drupe::Gateway::"trading"',
       {"shares": 25, "stock": "AMZN"},
   )

   assert decision == "Allow"

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

Event Schema
============

Dogwood has two schema layers:

* The **policy/action schema** is the Cedar ``.cedarschema`` file. It defines
  entities, actions, and request context types such as
  ``context.input.amount``.
* The **event schema** tells Dogwood how actions become historical events:
  which event kinds exist (``request``, ``response``, ``error``), which fields
  are recorded in the temporal history, and which event kinds produce
  authorization decisions.

The examples use Dogwood's default event schema. Under that default,
``request`` events are decision points, and the event history records request
``input`` fields plus reserved fields like ``callerPrincipal``,
``callerResource``, and ``requestId``. That is why a temporal policy can ask
about past events such as:

.. code-block:: text

   Drupe::Action::"Transfer"::request{ input.user: context.input.user }

In other words, the Cedar schema says what a ``Transfer`` request looks like;
the event schema says that ``Transfer::request`` is both authorizable and stored
in history for later temporal checks.

Python API
==========

.. code-block:: python

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

There is also a runnable example:

.. code-block:: bash

   make example

FastAPI Native Example
======================

The FastAPI example uses the native binding and a real Cedar schema. It loads
its own ``examples/fastapi_simple/policy.dw`` and
``examples/fastapi_simple/schema.cedarschema``, creates a persistent
``native.NativeAuthorizer``, and exposes an authorization endpoint.

The policy enforces a ``$50`` daily transfer limit per user. Three ``$20``
transfers by the same user produce:

.. code-block:: text

   Allow, Allow, Deny

Run it:

.. code-block:: bash

   make develop
   make examples-deps
   make fastapi-example

First transfer:

.. code-block:: bash

   curl -s http://127.0.0.1:8000/authorize \
     -H 'content-type: application/json' \
     -d '{"user":"alice","amount":20}'

Expected response:

.. code-block:: json

   {"decision":"Allow","allowed":true,"daily_limit":50}

Second transfer:

.. code-block:: bash

   curl -s http://127.0.0.1:8000/authorize \
     -H 'content-type: application/json' \
     -d '{"user":"alice","amount":20}'

Expected response:

.. code-block:: json

   {"decision":"Allow","allowed":true,"daily_limit":50}

Third transfer:

.. code-block:: bash

   curl -s http://127.0.0.1:8000/authorize \
     -H 'content-type: application/json' \
     -d '{"user":"alice","amount":20}'

Expected response:

.. code-block:: json

   {"decision":"Deny","allowed":false,"daily_limit":50}

Dogwood authorizers are stateful. The example keeps one shared native
authorizer and protects it with a lock. For high-throughput services, use a
pool or request-partitioned authorizers based on your temporal semantics.

The same FastAPI app also includes a quota-based rate limit endpoint:

.. code-block:: bash

   curl -s http://127.0.0.1:8000/authorize/quota \
     -H 'content-type: application/json' \
     -d '{"user":"carol","amount":1}'

That endpoint uses ``examples/fastapi_simple/quota_policy.dw``, which permits
fewer than three transfers by the same user within one hour. For one user, the
first two requests are allowed and the third is denied.

CLI
===

.. code-block:: bash

   dogwood-py validate policy.dw --policy-schema schema.cedarschema
   dogwood-py replay policy.dw --policy-schema schema.cedarschema --trace trace.log
   dogwood-py lower policy.dw --policy-schema schema.cedarschema

When using the local virtualenv directly:

.. code-block:: bash

   .venv/bin/dogwood-py validate policy.dw --policy-schema schema.cedarschema

Run the checked-in CLI example:

.. code-block:: bash

   make cli-example

Equivalent command:

.. code-block:: bash

   .venv/bin/dogwood-py replay examples/cli/policy.dw \
     --policy-schema examples/cli/schema.cedarschema \
     --trace examples/cli/trace.log

Expected output:

.. code-block:: text

   @0 (time point 0): true
   @1 (time point 1): false
