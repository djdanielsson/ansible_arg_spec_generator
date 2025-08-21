# Ansible Argument Specs Generator

[![Test Suite](https://github.com/djdanielsson/ansible_arg_spec_generator/actions/workflows/test.yml/badge.svg)](https://github.com/djdanielsson/ansible_arg_spec_generator/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/ansible-argument-spec-generator.svg)](https://badge.fury.io/py/ansible-argument-spec-generator)
[![Python Support](https://img.shields.io/pypi/pyversions/ansible-argument-spec-generator.svg)](https://pypi.org/project/ansible-argument-spec-generator/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool that automatically generates `argument_specs.yml` files for Ansible collections and roles. It analyzes your role's variables, tasks, and defaults to create comprehensive argument specifications that provide documentation and validation for your Ansible roles.

## Features

- **Collection-Wide Processing**: Process all roles in a collection automatically
- **Single Role Mode**: Generate specs for individual roles with interactive or automated modes
- **Intelligent Type Inference**: Automatically detects variable types based on naming patterns and usage
- **Variable Discovery**: Extracts variables from tasks, defaults, vars, and conditional statements
- **Smart Filtering**: Excludes registered variables, private variables, and Ansible built-ins
- **Multiple Entry Points**: Supports roles with multiple task entry points
- **Version Tracking**: Automatically adds `version_added` fields for new variables
- **Clean Output**: Generates well-formatted YAML with alphabetical sorting
- **Validation**: Built-in validation of generated specs

## Installation

```bash
# Install from PyPI
pip install ansible-argument-spec-generator

# Or install from source
pip install -e .
```

**Requirements:**
- Python 3.8+
- PyYAML (automatically installed)
- Ansible Core 2.11+ (for using the generated specs)

After installation, you have access to these commands:
- `ansible-argument-spec-generator`
- `generate-argument-spec` (shorter alias)

## Quick Start

```bash
# Process all roles in current collection
ansible-argument-spec-generator

# Process a single role interactively  
ansible-argument-spec-generator --single-role

# Get help
ansible-argument-spec-generator --help
```

## Usage

### Collection Mode (Default)

Process all roles in a collection:

```bash
# Process all roles in current collection
ansible-argument-spec-generator

# Process specific collection path
ansible-argument-spec-generator --collection-path /path/to/collection

# List roles in collection
ansible-argument-spec-generator --list-roles

# Process specific role only
ansible-argument-spec-generator --role my_role
```

### Single Role Mode

Process individual roles:

```bash
# Interactive mode
ansible-argument-spec-generator --single-role

# Generate from defaults file
ansible-argument-spec-generator --single-role --from-defaults defaults/main.yml

# Generate from configuration file
ansible-argument-spec-generator --single-role --from-config config.yml
```

### Verbosity Control

```bash
# Silent (default) - summary only
ansible-argument-spec-generator

# Basic info
ansible-argument-spec-generator -v

# Detailed processing
ansible-argument-spec-generator -vv

# Full debug output
ansible-argument-spec-generator -vvv
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--single-role` | Process individual role instead of entire collection |
| `--collection-path PATH` | Path to collection root (default: current directory) |
| `--list-roles` | List all roles found in collection |
| `--role NAME` | Process only the specified role |
| `--from-defaults FILE` | Generate specs from defaults file |
| `--from-config FILE` | Generate from configuration file |
| `--output FILE` | Output file path (default: meta/argument_specs.yml) |
| `--validate-only` | Validate existing specs without generating |
| `-v, -vv, -vvv` | Verbosity levels (basic, detailed, debug) |

## How It Works

The tool analyzes your Ansible roles to automatically generate argument specifications:

1. **Discovers Variables**: Extracts variables from `defaults/main.yml`, `vars/main.yml`, and task files
2. **Infers Types**: Automatically detects variable types based on naming patterns and default values
3. **Detects Entry Points**: Identifies multiple task entry points (main.yml, install.yml, etc.)
4. **Filters Variables**: Excludes registered variables, private variables, and Ansible built-ins
5. **Generates Specs**: Creates clean, well-formatted `argument_specs.yml` files

## Configuration File Format

For complex scenarios, create a configuration file:

```yaml
entry_points:
  main:
    short_description: "Install and configure web application"
    arguments:
      app_name:
        type: str
        required: true
        description: "Name of the application"
      
      state:
        type: str
        default: "present"
        choices: ["present", "absent", "started", "stopped"]
        description: "Desired state"
      
      app_port:
        type: int
        default: 8080
        description: "Port number"
    
    required_if:
      - ["state", "present", ["app_name"]]
```

## Generated Output

The tool creates standard `argument_specs.yml` files:

```yaml
---
argument_specs:
  main:
    short_description: "Auto-generated specs for webapp role"
    options:
      app_name:
        description: "Application name"
        type: str
        default: myapp
      
      app_enabled:
        description: "Enable application"
        type: bool
        default: true
      
      config_path:
        description: "Configuration file path"
        type: path
        default: /etc/myapp/config.yml
        version_added: "1.1.0"
...
```

## Variable Detection

The tool automatically extracts variables from multiple sources:

- **Defaults and Vars**: `defaults/main.yml` and `vars/main.yml`
- **Task Files**: Variables used in Jinja2 templates, conditionals, and loops
- **Multiple Entry Points**: Supports roles with `main.yml`, `install.yml`, `configure.yml`, etc.

### Smart Type Inference

Variables are automatically typed based on naming patterns:
- `*_path`, `*_dir`, `*_file` → `type: path`
- `*_enabled`, `*_debug`, `force_*` → `type: bool`
- `*_port`, `*_timeout` → `type: int`

### Variable Filtering

Automatically excludes:
- Private variables (starting with `__`)
- Registered variables from tasks
- Ansible built-ins (`ansible_facts`, `inventory_hostname`, etc.)

## Validation

Validate existing specs:

```bash
# Validate all roles
ansible-argument-spec-generator --validate-only

# Validate single role
ansible-argument-spec-generator --single-role --validate-only
```

## Integration with Ansible

Generated specs provide:
- **Documentation**: `ansible-doc --type role my_collection.my_role`
- **Validation**: Automatic argument validation
- **Error Messages**: Clear feedback for invalid inputs

## Examples

```bash
# Process entire collection
cd /path/to/my_collection
ansible-argument-spec-generator

# Process single role in collection
ansible-argument-spec-generator --role webapp

# Interactive single role mode
ansible-argument-spec-generator --single-role

# Generate from defaults file
ansible-argument-spec-generator --single-role --from-defaults defaults/main.yml
```

## Troubleshooting

### Common Issues

1. **"Not a collection root"**: Ensure you're in a directory with `galaxy.yml` and `roles/`
2. **"No roles found"**: Check that `roles/` directory contains valid role structures
3. **YAML parsing errors**: The tool provides specific error messages for malformed files
4. **File encoding issues**: Ensure all files are UTF-8 encoded

### Debugging

Use verbosity flags for troubleshooting:

```bash
# List roles in collection
ansible-argument-spec-generator --list-roles

# Validate existing specs
ansible-argument-spec-generator --validate-only

# Debug with verbosity
ansible-argument-spec-generator -vvv --role myrole
```

## License

MIT
