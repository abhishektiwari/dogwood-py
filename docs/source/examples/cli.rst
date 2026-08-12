CLI Example
===========

.. meta::
   :description: Run dogwood-py from the command line to validate, lower, and replay Dogwood policies with Cedar schemas and event schemas.
   :keywords: dogwood-py CLI, Dogwood replay, Dogwood validate, Dogwood lower, Cedar schema

The CLI exposes validation, replay, and lowering commands. Installed packages
provide ``dogwood`` as the preferred command and ``dogwood-py`` as a
backward-compatible alias:

.. code-block:: bash

   dogwood validate policy.dw --policy-schema schema.cedarschema
   dogwood replay policy.dw --policy-schema schema.cedarschema --trace trace.log
   dogwood lower policy.dw --policy-schema schema.cedarschema

With an explicit Dogwood event schema:

.. code-block:: bash

   dogwood replay policy.dw \
     --policy-schema schema.cedarschema \
     --event-schema event.dwschema \
     --trace trace.log

When using the local virtualenv directly:

.. code-block:: bash

   .venv/bin/dogwood validate policy.dw --policy-schema schema.cedarschema

Run the packaged CLI example:

.. code-block:: bash

   python -m examples.cli

The equivalent command from a source checkout is:

.. code-block:: bash

   dogwood replay examples/cli/policy.dw \
     --policy-schema examples/cli/schema.cedarschema \
     --trace examples/cli/trace.log

Expected output:

.. code-block:: text

   @0 (time point 0): true
   @1 (time point 1): false
