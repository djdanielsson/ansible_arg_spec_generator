"""
Ansible Argument Specs Generator

A comprehensive tool to generate argument_specs.yml files for Ansible collections and roles.
This tool helps automate the creation of argument specifications, which provide both 
documentation and validation for Ansible role variables.

Features:
- Collection-wide processing
- Smart variable filtering 
- Verbosity control
- Multiple entry points support
- Professional YAML output
"""

__version__ = "1.0.0.post1"
__author__ = "David Danielsson"
__email__ = "djdanielsson@users.noreply.github.com"

# Import main classes for programmatic use
try:
    from .generate_argument_specs import (
        ArgumentSpecsGenerator,
        ArgumentSpec,
        EntryPointSpec,
    )

    __all__ = ["ArgumentSpecsGenerator", "ArgumentSpec", "EntryPointSpec"]
except ImportError:
    # Handle case where module is run directly
    pass
