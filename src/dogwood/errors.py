class DogwoodError(Exception):
    """Base error for Dogwood SDK failures."""


class ParseError(DogwoodError):
    """Policy or trace input could not be parsed."""


class ValidationError(DogwoodError):
    """Policy validation failed."""


class UnsupportedFeatureError(DogwoodError):
    """The Python interpreter does not yet implement this Dogwood feature."""
