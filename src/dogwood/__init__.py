"""Python SDK for the Dogwood policy language."""

try:
    from ._version import version as __version__
except ImportError:
    try:
        from importlib.metadata import PackageNotFoundError, version

        __version__ = version("dogwood-py")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"

__author__ = "Abhishek Tiwari"

from .errors import DogwoodError, ParseError, UnsupportedFeatureError, ValidationError
from .enforcement import (
    EnforcementMode,
    EnforcementResult,
    PolicyEnforcer,
    apply_enforcement,
)
from .policy import (
    LoweredPolicySet,
    ParsedPolicy,
    ParsedPolicySet,
    PolicySchema,
    ServiceSchema,
    ValidationResult,
    Validator,
)
from .trace import parse_trace, replay_log
from .values import (
    Authorizer,
    Decision,
    Diagnostics,
    DogwoodRuleRef,
    Entity,
    Event,
    EventBuilder,
    Response,
    Value,
)

__all__ = [
    "Authorizer",
    "Decision",
    "Diagnostics",
    "DogwoodError",
    "DogwoodRuleRef",
    "Entity",
    "EnforcementMode",
    "EnforcementResult",
    "Event",
    "EventBuilder",
    "LoweredPolicySet",
    "ParseError",
    "ParsedPolicy",
    "ParsedPolicySet",
    "PolicySchema",
    "PolicyEnforcer",
    "Response",
    "ServiceSchema",
    "UnsupportedFeatureError",
    "ValidationError",
    "ValidationResult",
    "Validator",
    "Value",
    "__author__",
    "__version__",
    "apply_enforcement",
    "parse_trace",
    "replay_log",
]
