Installation
============

Install the latest release from PyPI:

.. code-block:: bash

   pip install dogwood-py

Install optional example dependencies:

.. code-block:: bash

   pip install "dogwood-py[examples]"


The package installs as :mod:`dogwood`.

.. code-block:: python

   from dogwood import native

   assert native.available()