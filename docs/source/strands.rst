Strands Agents Integration
==========================

.. meta::
   :description: Attach Dogwood temporal authorization policies to Strands Agents tool calls using dogwood-py interventions, plugins, hooks, and typed decisions.
   :keywords: Dogwood Strands Agents, dogwood-py Strands integration, agent tool authorization, agentic AI policy, Strands interventions

Dogwood policies should usually guard Strands tool calls through interventions.
Plugins and direct hooks are also available. All three surfaces support
Strands lifecycle events; before-tool-call authorization remains the default so
existing ``CallTool`` schemas do not accidentally deny invocation or model
events.

The implementation follows the Strands extension model:

* ``DogwoodIntervention`` subclasses Strands' intervention handler and returns
  typed actions.
* ``DogwoodPlugin`` subclasses Strands' plugin base class and uses ``@hook`` so
  Strands can auto-register lifecycle handlers from their event types.
* ``lifecycle_hook`` exposes lower-level lifecycle hooks when you need direct
  event mutation.

Supported lifecycle names:

* ``before_invocation``
* ``after_invocation``
* ``message_added``
* ``before_model_call``
* ``after_model_call``
* ``before_tool_call``
* ``after_tool_call``

Before-events can block execution when Dogwood denies. After-events are
observational by default because the work has already happened; use them to
record outcomes into Dogwood temporal history or guide the next model step.

Install the optional Strands dependency:

.. code-block:: bash

   pip install "dogwood-py[strands]"

Intervention handler
--------------------

Use ``DogwoodIntervention`` when you want Strands' typed control flow. It
returns ``Proceed`` for allowed tool calls, ``Deny`` for hard denials, and can
return ``Confirm`` for human step-up approval.

.. code-block:: python

   from strands import Agent
   from dogwood.integrations.strands import DogwoodIntervention

   dogwood_policy = DogwoodIntervention(
       policy_source=policy_source,
       policy_schema_source=cedar_schema_source,
       event_schema_source=event_schema_source,
   )

   agent = Agent(
       tools=[search_tool, write_file],
       interventions=[dogwood_policy],
   )

To evaluate more lifecycle stages, pass ``lifecycle_events``:

.. code-block:: python

   dogwood_policy = DogwoodIntervention(
       policy_source=policy_source,
       policy_schema_source=cedar_schema_source,
       event_schema_source=event_schema_source,
       lifecycle_events=(
           "before_invocation",
           "before_tool_call",
           "after_tool_call",
           "before_model_call",
           "after_model_call",
       ),
   )

Use ``lifecycle_events="all"`` to evaluate every supported lifecycle event.

Structural checks that should happen before Dogwood policy evaluation belong in
agent code as a separate intervention before ``DogwoodIntervention``. This is
where you can normalize model-generated tool input with ``transform(...)`` or
give the model corrective feedback with ``guide(...)``.

.. code-block:: python

   from strands.interventions import InterventionHandler
   from dogwood.integrations.strands import DogwoodIntervention, guide, proceed

   class ToolInputPrecheck(InterventionHandler):
       name = "tool-input-precheck"

       def before_tool_call(self, event, **kwargs):
           tool_input = event.tool_use["input"]
           if event.tool_use["name"] == "send_email" and not tool_input.get("subject"):
               return guide("All emails must include a subject line.")
           return proceed()

   dogwood_policy = DogwoodIntervention(
       policy_source=policy_source,
       policy_schema_source=cedar_schema_source,
       event_schema_source=event_schema_source,
   )

   agent = Agent(
       tools=[send_email],
       interventions=[ToolInputPrecheck(), dogwood_policy],
   )

For step-up approval, pass ``confirm_when``. It can be ``True``, a prompt
string, or a function that returns ``False``, ``True``, or a custom prompt.

.. code-block:: python

   high_risk_policy = DogwoodIntervention(
       policy_source=item_risk_policy,
       policy_schema_source=cedar_schema_source,
       event_schema_source=event_schema_source,
       confirm_when=lambda event: (
           "Approve this high-risk item?"
           if event.tool_use["name"] == "add_to_cart"
           else False
       ),
   )

Plugin
------

Use ``DogwoodPlugin`` when you want Strands to discover and register decorated
plugin hooks automatically. The plugin exposes hook methods for invocation,
message, model, and tool lifecycle events.

.. code-block:: python

   from strands import Agent
   from dogwood.integrations.strands import DogwoodPlugin

   agent = Agent(
       tools=[search_tool, write_file],
       plugins=[
           DogwoodPlugin(
               policy_source=policy_source,
               policy_schema_source=cedar_schema_source,
               event_schema_source=event_schema_source,
               lifecycle_events="all",
           )
       ],
   )

Direct hook
-----------

Use ``before_tool_call_hook`` if you need the lower-level hook object directly
for tool authorization. Denied calls set ``event.cancel_tool``.

.. code-block:: python

   from strands import Agent
   from dogwood.integrations.strands import before_tool_call_hook

   agent = Agent(
       tools=[search_tool, write_file],
       hooks=[
           before_tool_call_hook(
               policy_source=policy_source,
               policy_schema_source=cedar_schema_source,
               event_schema_source=event_schema_source,
           )
       ],
   )

The default hook maps a Strands tool call into Dogwood input like this:

.. code-block:: python

   {
       "tool": event.tool_use["name"],
       "input": event.tool_use["input"],
       "toolUseId": event.tool_use.get("toolUseId", ""),
   }

The default request action is ``Drupe::Action::CallTool``. The Dogwood policy
source still refers to the Cedar action as ``Drupe::Action::"CallTool"``.
The principal and resource can be supplied through Strands
``invocation_state``:

.. code-block:: python

   agent(
       "research Dogwood policy examples",
       principal='Drupe::OAuthUser::"alice"',
       resource='Drupe::Gateway::"agent"',
   )

For framework-specific semantics, pass custom ``principal``, ``resource``, or
``input_mapper`` callbacks when constructing the hook.

Use ``lifecycle_hook`` for direct access to all lifecycle stages:

.. code-block:: python

   from dogwood.integrations.strands import lifecycle_hook

   dogwood_lifecycle = lifecycle_hook(
       policy_source=policy_source,
       policy_schema_source=cedar_schema_source,
       event_schema_source=event_schema_source,
       lifecycle_events="all",
   )

   dogwood_lifecycle.handle("before_invocation", event)
   dogwood_lifecycle.handle("after_tool_call", event)

Example
-------

See :doc:`examples/strands-shopping-agent` for the runnable shopping-agent
example. It uses framework-neutral policies from
``examples/shopping_agent_policies`` and Strands-specific wiring from
``examples/strands_shopping_agent``.

