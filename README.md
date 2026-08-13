# Ansible Argument Specs Generator

[![Test Suite](https://github.com/djdanielsson/ansible_arg_spec_generator/actions/workflows/test.yml/badge.svg)](https://github.com/djdanielsson/ansible_arg_spec_generator/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/ansible-argument-spec-generator.svg)](https://badge.fury.io/py/ansible-argument-spec-generator)
[![Python Support](https://img.shields.io/pypi/pyversions/ansible-argument-spec-generator.svg)](https://pypi.org/project/ansible-argument-spec-generator/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool that automatically generates `argument_specs.yml` files for Ansible collections and roles. It analyzes your role's variables, tasks, and defaults to create comprehensive argument specifications that provide documentation and validation for your Ansible roles.

## Features

- **Collection-Wide Processing**: Process all roles in a collection automatically
- **Single Role Mode**: Generate specs for individual roles with interactive or automated modes
- **Intelligent Type Inference**: Detects types from default values (and path-like names/values)
- **Variable Discovery**: Extracts variables from `defaults/*.yml`, tasks, and templates (`vars/` via `--include-vars`)
- **Secret Handling**: Sets `no_log: true` for password/token/secret-like names
- **Smart Filtering**: Excludes registered variables, private (`_`-prefixed) variables, and Ansible built-ins
- **Multiple Entry Points**: Supports roles with multiple task entry points
- **Spec Preservation**: Keeps curated types, choices, conditionals, and `no_log` on regenerate
- **Safe Writes**: Timestamped `.bak` backups before overwrite (disable with `--no-backup`)
- **Version Tracking**: Automatically adds `version_added` for newly discovered variables
- **Validation**: Checks types, required/default conflicts, choices, elements, and conditionals

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
# Default - final summary only
ansible-argument-spec-generator

# Basic info
ansible-argument-spec-generator -v

# Detailed processing
ansible-argument-spec-generator -vv

# Full debug output
ansible-argument-spec-generator -vvv

# Suppress all output (including summaries)
ansible-argument-spec-generator --quiet
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
| `--include-vars` | Include variables from `vars/` as options (off by default) |
| `--no-backup` | Skip timestamped `.bak` backup before overwrite |
| `--dry-run` | Preview output without writing files |
| `-q, --quiet` | Suppress all output including summaries |
| `-v, -vv, -vvv` | Verbosity levels (basic, detailed, debug) |

## How It Works

The tool analyzes your Ansible roles to automatically generate argument specifications:

1. **Discovers Variables**: Extracts variables from `defaults/*.yml`, task files, and templates (`vars/` only with `--include-vars`)
2. **Infers Types**: Automatically detects variable types based on naming patterns and default values
3. **Marks Secrets**: Sets `no_log: true` for password/token/secret-like variable names
4. **Detects Entry Points**: Identifies multiple task entry points (main.yml, install.yml, etc.)
5. **Filters Variables**: Excludes registered variables, private variables, and Ansible built-ins
6. **Preserves Curated Specs**: Keeps existing types, choices, conditionals, and `no_log` on regenerate
7. **Generates Specs**: Creates clean `argument_specs.yml` files (with timestamped backups by default)

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
      app_enabled:
        description: "Enable application"
        type: bool
        default: true

      app_password:
        description: "Password for authentication"
        type: str
        default: changeme
        no_log: true

      config_path:
        description: "Configuration file path"
        type: path
        default: /etc/myapp/config.yml
        version_added: "1.1.0"
...
```

## Variable Detection

The tool automatically extracts variables from multiple sources:

- **Defaults**: all `defaults/*.yml` / `defaults/*.yaml` (merged; `main.yml` first)
- **Vars** (optional): all `vars/*.yml` when `--include-vars` is set
- **Task Files**: Jinja2 usages, conditionals, loops, asserts, environment, tags
- **Templates**: Jinja2 variables under `templates/`
- **Multiple Entry Points**: standalone task files not included by others (plus `main`)

Vars values may still be used for **type inference** when a variable appears in tasks/templates, even if `--include-vars` is off.

### Smart Type Inference

Types come primarily from default values:
- Python `bool` / `int` / `float` / `list` / `dict` → matching Ansible types
- Path-like names (`*_path`, `*_dir`, …) with path-like values → `type: path`
- List element types are inferred from list contents (`bool` checked before `int`)
- Secret-like names (`password`, `token`, `secret`, …) → `no_log: true`

### Variable Filtering

Automatically excludes:
- Private variables (names starting with `_`)
- Registered variables and `set_fact` names from tasks
- Ansible built-ins (`ansible_*`, and exact names like `item`, `loop`, `hostvars`, `inventory_hostname`, …)

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

# Include vars/ as options and skip backups
ansible-argument-spec-generator --include-vars --no-backup

# Preview without writing files
ansible-argument-spec-generator --dry-run

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

## Contributing

We welcome contributions! Here's how you can help improve the Ansible Argument Specs Generator:

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/djdanielsson/ansible_arg_spec_generator.git
   cd ansible_arg_spec_generator
   ```

2. **Set up development environment:**
   ```bash
   # Install Python 3.8+
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Run tests:**
   ```bash
   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=generate_argument_specs --cov-report=html

   # Run specific test categories
   pytest -k "test_basic"
   ```

4. **Code formatting:**
   ```bash
   # Format code with Black
   black .

   # Check formatting
   black --check .
   ```

### Development Guidelines

- **Code Style:** Follow PEP 8 guidelines
- **Formatting:** Use Black for consistent formatting
- **Testing:** Write tests for new features and bug fixes
- **Documentation:** Update README and docstrings for changes
- **Commits:** Use clear, descriptive commit messages

### Testing

The project includes comprehensive tests covering:
- Core functionality
- Edge cases
- Integration tests
- CI/CD workflows

Run the full test suite:
```bash
pytest tests/ -v
```

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest`
5. Format code: `black .`
6. Commit your changes: `git commit -m "Add your feature"`
7. Push to your fork: `git push origin feature/your-feature`
8. Create a Pull Request

### Bug Reports and Feature Requests

- **Bug Reports:** Use GitHub Issues with detailed reproduction steps
- **Feature Requests:** Describe the proposed feature and its use case
- **Questions:** Check existing issues or create a discussion

### Code of Conduct

This project follows a code of conduct to ensure a welcoming environment for all contributors.

## License

MIT
