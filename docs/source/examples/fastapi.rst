FastAPI Native Example
======================

The FastAPI example uses the native binding and a real Cedar schema. It loads
its own ``examples/fastapi_simple/policy.dw`` and
``examples/fastapi_simple/schema.cedarschema`` plus
``examples/fastapi_simple/event.dwschema``, creates a persistent
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
