Dogwood Policy Python SDK
=========================

.. meta::
   :description: dogwood-py is a Python SDK and PyO3 binding for Dogwood, a Cedar-compatible temporal authorization policy language for Python, FastAPI, CLIs, and Strands Agents.
   :keywords: Dogwood, dogwood-py, Python SDK, authorization, Cedar policy, temporal policy, PyO3, maturin, FastAPI, Strands Agents

Python SDK and PyO3 binding for the `Dogwood <https://github.com/dogwood-policy/dogwood>`_
policy language. Dogwood is a policy language for fine-grained authorization
decisions that depend on history or patterns of events over time - not just a
single request. It adds temporal conditions (since, formerly, once,
aggregations) and information providers (computed guardrail facts) on top of
`Cedar <https://www.cedarpolicy.com/>`_ policy syntax, then lowers everything
back to Cedar for evaluation. Existing Cedar policies stay valid as-is. For
information, read the `Dogwood documentation <https://dogwood-policy.github.io/dogwood/index.html>`_.

.. warning::

   Current Dogwood reference interpreter is not intended for production use;
   therefore, this Python SDK and PyO3 binding is experimental in nature.

.. note::

   This is an unofficial Python SDK and port for Dogwood Policy. Support is
   provided on a best effort basis with community help.

|github-release| |tests| |pypi-version| |python-wheels| |python-versions|
|last-commit| |pypi-status| |conda-version| |license| |github-downloads|
|pypi-downloads|

.. |github-release| image:: https://img.shields.io/github/v/release/abhishektiwari/dogwood-py
   :alt: GitHub Release

.. |tests| image:: https://img.shields.io/github/actions/workflow/status/abhishektiwari/dogwood-py/test.yml?label=tests
   :alt: GitHub Actions Test Workflow Status

.. |pypi-version| image:: https://img.shields.io/pypi/v/dogwood-py
   :alt: PyPI Version

.. |python-wheels| image:: https://img.shields.io/pypi/wheel/dogwood-py
   :alt: Python Wheels

.. |python-versions| image:: https://img.shields.io/pypi/pyversions/dogwood-py?logo=python&logoColor=white
   :alt: Python Versions

.. |last-commit| image:: https://img.shields.io/github/last-commit/abhishektiwari/dogwood-py
   :alt: GitHub Last Commit

.. |pypi-status| image:: https://img.shields.io/pypi/status/dogwood-py
   :alt: PyPI Status

.. |conda-version| image:: https://img.shields.io/conda/v/dogwood-py/dogwood-py
   :alt: Conda Version

.. |license| image:: https://img.shields.io/github/license/abhishektiwari/dogwood-py
   :alt: License

.. |github-downloads| image:: https://img.shields.io/github/downloads/abhishektiwari/dogwood-py/total?label=GitHub%20Downloads
   :alt: GitHub Downloads

.. |pypi-downloads| image:: https://img.shields.io/pepy/dt/dogwood-py?label=PyPI%20Downloads
   :alt: PyPI Downloads

The public API is modeled after the Rust ``dogwood-language`` lifecycle:

1. Build a ``ServiceSchema`` and ``PolicySchema``.
2. Parse and lower policy source into a ``LoweredPolicySet``.
3. Validate it.
4. Feed ``Event`` values to a stateful ``Authorizer``.

This package uses PyO3/maturin to bind the Rust ``dogwood-language`` reference
for schema-backed lowering, validation, and trace replay. The Python SDK also
keeps a temporary pure-Python fallback only for source-tree examples that omit
a full Cedar action schema. Schema-backed workflows require the native
extension.

The SDK includes :class:`dogwood.PolicyEnforcer` with ``enforce`` and
``log_only`` modes for rollout and audit behavior. Dogwood still evaluates the
policy; the SDK mode controls whether a denied result blocks execution or is
reported as ``would_have_denied``. See
:mod:`dogwood.enforcement` for the API reference.

``dogwood-py`` also provides optional Strands Agents support. Dogwood policies can
be attached as Strands interventions so tool calls are checked before execution,
with typed outcomes such as proceed, deny, guide, confirm, and transform. See
:doc:`strands` for the integration API and
:doc:`examples/strands-shopping-agent` for a runnable shopping-agent example.

Strands integrations use the same SDK-level ``enforce`` and ``log_only`` modes
on top of the Rust Dogwood policy decision.


.. toctree::
   :maxdepth: 1
   :caption: User Guide

   installation
   getting-started
   native
   strands
   examples/index
   api



Project Links
-------------

* `GitHub <https://github.com/abhishektiwari/dogwood-py>`_
* `PyPI <https://pypi.org/project/dogwood-py/>`_
* `Dogwood documentation <https://dogwood-policy.github.io/dogwood/index.html>`_
