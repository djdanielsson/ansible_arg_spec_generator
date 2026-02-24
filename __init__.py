"""
Ansible Argument Specs Generator

A comprehensive tool to generate argument_specs.yml files for Ansible collections and roles.
"""

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("ansible-argument-spec-generator")
except Exception:
    __version__ = "1.1.0"

__author__ = "David Danielsson"
__email__ = "djdanielsson@users.noreply.github.com"

try:
    from .generate_argument_specs import (
        ArgumentSpecsGenerator,
        ArgumentSpec,
        EntryPointSpec,
        GeneratorError,
        CollectionNotFoundError,
        RoleNotFoundError,
        ConfigError,
        ValidationError,
    )

    __all__ = [
        "ArgumentSpecsGenerator",
        "ArgumentSpec",
        "EntryPointSpec",
        "GeneratorError",
        "CollectionNotFoundError",
        "RoleNotFoundError",
        "ConfigError",
        "ValidationError",
    ]
except ImportError:
    pass
