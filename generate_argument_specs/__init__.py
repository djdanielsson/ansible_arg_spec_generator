"""
Ansible Argument Specs Generator

A Python package to generate argument_specs.yml files for Ansible roles.
Supports multiple input methods and validates the generated specs.
"""

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("ansible-argument-spec-generator")
except Exception:
    __version__ = "1.1.0"

from generate_argument_specs._cli import create_example_config, main
from generate_argument_specs._exceptions import (
    CollectionNotFoundError,
    ConfigError,
    GeneratorError,
    RoleNotFoundError,
    ValidationError,
)
from generate_argument_specs._generator import ArgumentSpecsGenerator
from generate_argument_specs._models import ArgumentSpec, ArgumentType, EntryPointSpec

__all__ = [
    "__version__",
    "ArgumentSpecsGenerator",
    "ArgumentSpec",
    "ArgumentType",
    "EntryPointSpec",
    "GeneratorError",
    "CollectionNotFoundError",
    "RoleNotFoundError",
    "ConfigError",
    "ValidationError",
    "main",
    "create_example_config",
]
