Strands Shopping Agent
======================

.. meta::
   :description: Run a Strands shopping agent example where dogwood-py policies control session access, checkout approval, item risk, daily budget, and order quota.
   :keywords: Strands shopping agent, dogwood-py agent policy, agent tool authorization, shopping agent guardrails

The Strands example models a shopping agent protected by Dogwood policies for
session access, login before checkout, checkout approval, high-risk item
step-up, daily budget, daily order quota, and tool sequencing.

Run it:

.. code-block:: bash

   make strands-shopping-agent ARGS="--user alice"

This opens an interactive console:

.. code-block:: text

   shopping-agent> grant
   shopping-agent> products
   shopping-agent> add iphone17-case 2
   shopping-agent> login
   shopping-agent> approve
   shopping-agent> checkout

The reusable shopping-agent policies live in
``examples/shopping_agent_policies``. The Strands-specific wiring lives in
``examples/strands_shopping_agent``.

See :doc:`/strands` for the integration API and intervention details.
