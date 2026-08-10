"""Strands Agents integration for Dogwood policy enforcement.

The integration follows the Strands extension model:

* :class:`DogwoodIntervention` implements typed intervention decisions for
  before-tool-call authorization.
* :class:`DogwoodPlugin` subclasses ``strands.plugins.Plugin`` and uses a
  decorated hook for automatic plugin registration.
* :func:`lifecycle_hook` exposes lifecycle-aware hooks directly.

All three surfaces use a persistent Dogwood native authorizer so policy parsing
and lowering happen once per integration object.
"""

from dogwood.integrations.strands.common import (
    IdentityResolver,
    InputMapper,
    default_lifecycle_input,
    default_principal,
    default_resource,
    default_tool_input,
)
from dogwood.integrations.strands.hooks import (
    ALL_LIFECYCLE_EVENTS,
    DEFAULT_LIFECYCLE_EVENTS,
    StrandsLifecyclePolicyHook,
    StrandsPolicyHook,
    attach_before_tool_call_hook,
    before_tool_call_hook,
    lifecycle_hook,
)
from dogwood.integrations.strands.intervention import (
    DogwoodIntervention,
    confirm,
    deny,
    guide,
    proceed,
    transform,
)
from dogwood.integrations.strands.plugin import DogwoodPlugin

__all__ = [
    "DogwoodIntervention",
    "DogwoodPlugin",
    "ALL_LIFECYCLE_EVENTS",
    "DEFAULT_LIFECYCLE_EVENTS",
    "IdentityResolver",
    "InputMapper",
    "StrandsLifecyclePolicyHook",
    "StrandsPolicyHook",
    "attach_before_tool_call_hook",
    "before_tool_call_hook",
    "confirm",
    "default_lifecycle_input",
    "default_principal",
    "default_resource",
    "default_tool_input",
    "deny",
    "guide",
    "lifecycle_hook",
    "proceed",
    "transform",
]
