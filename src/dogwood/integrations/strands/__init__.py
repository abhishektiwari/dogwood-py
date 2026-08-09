"""Strands Agents integration for Dogwood policy enforcement."""

from dogwood.integrations.strands.common import (
    IdentityResolver,
    InputMapper,
    default_principal,
    default_resource,
    default_tool_input,
)
from dogwood.integrations.strands.hooks import (
    StrandsPolicyHook,
    attach_before_tool_call_hook,
    before_tool_call_hook,
)
from dogwood.integrations.strands.intervention import DogwoodIntervention
from dogwood.integrations.strands.plugin import DogwoodPlugin

__all__ = [
    "DogwoodIntervention",
    "DogwoodPlugin",
    "IdentityResolver",
    "InputMapper",
    "StrandsPolicyHook",
    "attach_before_tool_call_hook",
    "before_tool_call_hook",
    "default_principal",
    "default_resource",
    "default_tool_input",
]
