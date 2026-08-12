Installation
============

Install the latest release from PyPI:

.. code-block:: bash

   pip install dogwood-py

Install optional example dependencies. The ``examples`` extra covers FastAPI
and general example dependencies. The ``strands`` extra is required for the
Strands integration and the Strands shopping-agent example:

.. code-block:: bash

   pip install "dogwood-py[examples]"
   pip install "dogwood-py[strands]"
   pip install "dogwood-py[examples,strands]"


The package installs as :mod:`dogwood`.

.. code-block:: python

   from dogwood import native

   assert native.available()
