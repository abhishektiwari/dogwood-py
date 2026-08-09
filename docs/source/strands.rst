Strands Agents Integration
==========================

.. meta::
   :description: Attach Dogwood temporal authorization policies to Strands Agents tool calls using dogwood-py interventions, plugins, hooks, and typed decisions.
   :keywords: Dogwood Strands Agents, dogwood-py Strands integration, agent tool authorization, agentic AI policy, Strands interventions

Dogwood policies should usually guard Strands tool calls through interventions.
Plugins and direct hooks are still available for lower-level integration. All
three use ``BeforeToolCallEvent`` semantics: Dogwood authorizes the selected
tool before Strands invokes it.

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
plugin hooks automatically.

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
           )
       ],
   )

Direct hook
-----------

Use ``before_tool_call_hook`` if you need the lower-level hook object directly.
Denied calls set ``event.cancel_tool``.

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

Example
-------

See :doc:`examples/strands-shopping-agent` for the runnable shopping-agent
example. It uses framework-neutral policies from
``examples/shopping_agent_policies`` and Strands-specific wiring from
``examples/strands_shopping_agent``.
