Getting Started With dogwood-py
===============================

.. meta::
   :description: Build your first Dogwood temporal authorization policy in Python with dogwood-py, Cedar schemas, Dogwood event schemas, native replay, and validation.
   :keywords: dogwood-py getting started, Dogwood Python SDK, temporal authorization, Cedar schema, Dogwood event schema

This page walks through a first Dogwood authorization with ``dogwood-py``: a
Cedar action schema, a Dogwood event schema, a policy, and Python code that
decides a request. It starts with a single-request policy and then adds a
decision that depends on history.

The Shape Of The Workflow
-------------------------

Every schema-backed Dogwood workflow follows the same pipeline:

* Build the two schema halves: a ``ServiceSchema`` for Dogwood service inputs
  such as the event-schema DSL, and a ``PolicySchema`` for your Cedar action
  schema.
* Parse and lower policy source into a ``LoweredPolicySet``.
* Validate the lowered policy set.
* Build an authorizer and feed it events or request-like tool calls.

The native Python binding also exposes a convenience ``NativeAuthorizer``. It
parses and lowers once, then handles repeated authorization calls.

Step 1 - Install
----------------

Install from PyPI:

.. code-block:: bash

   pip install dogwood-py

For local development from this repository:

.. code-block:: bash

   make develop

The package installs as :mod:`dogwood`:

.. code-block:: python

   from dogwood import native

   assert native.available()

Step 2 - A Cedar Action Schema
------------------------------

The action schema declares the entity types and actions in your application. It
is standard Cedar ``.cedarschema`` text. This minimal schema has ``Login`` and
``Read`` actions. Each action input lives under ``context.input``.

.. code-block:: text

   namespace Drupe {
     type LoginInput = { user: String };
     type LoginOutput = { success: Bool };
     type ReadInput = { user: String };

     entity Gateway;
     entity OAuthUser;

     action "Login" appliesTo {
       principal: [OAuthUser],
       resource: [Gateway],
       context: { input: LoginInput, output?: LoginOutput }
     };

     action "Read" appliesTo {
       principal: [OAuthUser],
       resource: [Gateway],
       context: { input: ReadInput }
     };
   }

Step 3 - A Dogwood Event Schema
-------------------------------

Dogwood has two schema layers:

* The **policy/action schema** is the Cedar ``.cedarschema`` file. It defines
  entities, actions, and request context types such as
  ``context.input.amount``.
* The **event schema** tells Dogwood how actions become historical events:
  which event kinds exist, which fields are recorded in temporal history, and
  which event kinds produce authorization decisions.

The default event schema is usable for many cases, but an explicit
``.dwschema`` makes the event model visible and portable.

.. code-block:: text

   decision event <A>::request {
       ...inputs(A),
       pin callerPrincipal: principalType(A) = principal,
       callerResource: resourceType(A),
       requestId: String,
       sessionId: String,
   }

   event <A>::response {
       ...inputs(A),
       ...outputs(A),
       pin callerPrincipal: principalType(A) = principal,
       callerResource: resourceType(A),
       requestId: String,
       sessionId: String,
   }

The ``decision`` prefix means ``request`` events produce authorization
decisions. The ``callerPrincipal`` pin keeps temporal history local to the
requesting principal.

Under Dogwood's default event schema, ``request`` events are decision points,
and the event history records request ``input`` fields plus reserved fields
like ``callerPrincipal``, ``callerResource``, and ``requestId``. That is why a
temporal policy can ask about past events such as:

.. code-block:: text

   Drupe::Action::"Transfer"::request{ input.user: context.input.user }

In other words, the Cedar schema says what a ``Transfer`` request looks like;
the event schema says that ``Transfer::request`` is both authorizable and
stored in history for later temporal checks.

To supply an explicit event schema through the high-level API, pass
``ServiceSchema(event_schema=...)``:

.. code-block:: python

   from pathlib import Path

   service = ServiceSchema(event_schema=Path("event.dwschema").read_text())
   policies = LoweredPolicySet.from_str(policy, service, policy_schema)

Step 4 - A Policy
-----------------

A policy is a ``permit`` or ``forbid`` rule. This one permits every ``Read``
request.

.. code-block:: text

   @id("permit_read_anyone")
   permit (
       principal,
       action == Drupe::Action::"Read",
       resource
   );

Step 5 - Decide From Python
---------------------------

Use the native authorizer for schema-backed workflows. It is persistent, so the
policy is parsed and lowered once.

.. code-block:: python

   from dogwood import native

   authorizer = native.NativeAuthorizer(
       policy_source,
       cedar_schema_source,
       event_schema_source,
   )

   decision = authorizer.authorize_request(
       "Drupe::Action::Read",
       'Drupe::OAuthUser::"alice"',
       'Drupe::Gateway::"gw1"',
       {"user": "alice"},
   )

   assert decision == "Allow"

Use the higher-level SDK objects when you want the full parse/lower/validate
shape in Python:

.. code-block:: python

   from dogwood import LoweredPolicySet, PolicySchema, ServiceSchema, Validator

   service = ServiceSchema(event_schema=event_schema_source)
   policy_schema = PolicySchema.from_cedarschema_str(cedar_schema_source)
   policies = LoweredPolicySet.from_str(policy_source, service, policy_schema)

   assert Validator().validate(policies).validation_passed()

Step 6 - A Decision That Depends On History
-------------------------------------------

Now change the requirement: permit ``Read`` only if the same user logged in
within the last hour.

.. code-block:: text

   @id("read_after_login")
   permit (
       principal,
       action == Drupe::Action::"Read",
       resource
   )
   when temporal {
       formerly within 1h Drupe::Action::"Login"::response{
           input.user: context.input.user
       }
   };

Read the temporal clause as: there was formerly, within the last hour, a
successful ``Login`` whose ``input.user`` matches this ``Read`` request.

Replay a trace with the native binding:

.. code-block:: python

   trace = '''
   @0 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "r1", sessionId: "s1")
   @5 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::response(input: { user: "alice" }, output: { success: true }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "r1", sessionId: "s1")
   @10 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "r2", sessionId: "s1")
   @7200 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "r3", sessionId: "s1")
   '''

   print(native.replay(
       temporal_policy_source,
       cedar_schema_source,
       trace,
       event_schema_source,
   ))

Output:

.. code-block:: text

   @0 (time point 0): false
   @10 (time point 2): true
   @7200 (time point 3): false

The login request at ``@0`` is denied because the policy only permits
``Read``. The login response at ``@5`` is history-only. The read at ``@10`` is
allowed because the login response is within one hour. The read at ``@7200`` is
denied because the login has expired.

Run It From The CLI
-------------------

Save the policy, Cedar action schema, Dogwood event schema, and trace to files,
then run:

.. code-block:: bash

   dogwood-py validate policy.dw \
     --policy-schema schema.cedarschema \
     --event-schema event.dwschema

   dogwood-py replay policy.dw \
     --policy-schema schema.cedarschema \
     --event-schema event.dwschema \
     --trace trace.log

Checked-in runnable examples are available under ``examples/``:

.. code-block:: bash

   make cli-example
   make fastapi-example
   make strands-shopping-agent

Where To Go Next
----------------

* :doc:`native` covers native versus non-native execution.
* :doc:`api` lists the generated Python API reference.
* :doc:`examples/index` covers the CLI, FastAPI, and shopping-agent examples.
* :doc:`strands` covers Strands Agents interventions, plugins, and the shopping
  agent example.
* `Dogwood documentation <https://dogwood-policy.github.io/dogwood/index.html>`_
  covers the language, temporal expressions, macros, and provider schemas in
  depth.
