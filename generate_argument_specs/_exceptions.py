"""
Exception hierarchy for the argument spec generator.
"""


class GeneratorError(Exception):
    """Base exception for argument spec generator errors."""


class CollectionNotFoundError(GeneratorError):
    """Raised when a collection root cannot be found."""


class RoleNotFoundError(GeneratorError):
    """Raised when a specified role cannot be found."""


class ConfigError(GeneratorError):
    """Raised for configuration file errors."""


class ValidationError(GeneratorError):
    """Raised when spec validation fails."""
