CLI Example
===========

The CLI exposes validation, replay, and lowering commands:

.. code-block:: bash

   dogwood-py validate policy.dw --policy-schema schema.cedarschema
   dogwood-py replay policy.dw --policy-schema schema.cedarschema --trace trace.log
   dogwood-py lower policy.dw --policy-schema schema.cedarschema

With an explicit Dogwood event schema:

.. code-block:: bash

   dogwood-py replay policy.dw \
     --policy-schema schema.cedarschema \
     --event-schema event.dwschema \
     --trace trace.log

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
