# Ansible Argument Specs Generator

[![Test Suite](https://github.com/djdanielsson/ansible_arg_spec_generator/actions/workflows/test.yml/badge.svg)](https://github.com/djdanielsson/ansible_arg_spec_generator/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/djdanielsson/ansible_arg_spec_generator/branch/main/graph/badge.svg)](https://codecov.io/gh/djdanielsson/ansible_arg_spec_generator)
[![PyPI version](https://badge.fury.io/py/ansible-argument-spec-generator.svg)](https://badge.fury.io/py/ansible-argument-spec-generator)
[![Python Support](https://img.shields.io/pypi/pyversions/ansible-argument-spec-generator.svg)](https://pypi.org/project/ansible-argument-spec-generator/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Python script to generate `argument_specs.yml` files for Ansible collections and individual roles. This tool helps automate the creation of argument specifications, which provide both documentation and validation for Ansible role variables.

## Features

- **Collection-Wide Processing**: Automatically processes all roles in a collection (default mode)
- **Single Role Mode**: Interactive and automated processing for individual roles
- **Multiple Input Methods**: Interactive mode, generate from existing defaults files, or use configuration files
- **Full Validation**: Validates generated specs and checks for common errors
- **Conditional Requirements**: Supports `required_if`, `required_one_of`, `mutually_exclusive`, and `required_together`
- **Enhanced Type Inference**: Intelligently infers argument types with context-aware detection (paths, URLs, states, etc.)
- **Comprehensive Variable Detection**: Extracts variables from task files, assert statements, failed_when, changed_when conditions
- **Smart Variable Filtering**: Automatically excludes registered variables, private variables (`__*`), and Ansible built-ins
- **Smart Required Detection**: Variables without defaults automatically marked as required
- **Smart Descriptions**: Generates meaningful descriptions based on variable naming patterns and usage context
- **Automatic Version Tracking**: Adds `version_added` field for new variables based on collection/role version
- **Entry Points**: Support for multiple entry points in a single role with automatic detection
- **Verbosity Control**: Silent default mode with progressive verbosity levels (-v, -vv, -vvv)
- **Alphabetical Sorting**: Options sorted alphabetically for consistent, readable output
- **Clean YAML Output**: No reference anchors, proper formatting with document markers
- **Robust Error Handling**: Comprehensive error handling with specific error types and informative messages
- **Standards Compliant**: Generates specs compatible with Ansible Core 2.11+

## Installation

### Recommended: Install via pip

Install the package from your local development copy:

```bash
pip install -e .
```

**Requirements:**
- Python 3.6+
- PyYAML (automatically installed)
- Ansible Core 2.11+ (for using the generated specs)

After installation, you'll have access to these command-line tools:
- `ansible-argument-spec-generator` (primary command)
- `generate-argument-spec` (shorter alternative)

Both commands are functionally identical - use whichever you prefer!

### Quick Start

```bash
# Install the package
pip install -e .

# Process all roles in current collection
ansible-argument-spec-generator
# or use the shorter command:
generate-argument-spec

# Process a single role interactively  
ansible-argument-spec-generator --single-role

# Get help with all options
ansible-argument-spec-generator --help
```

### Alternative: Direct Script Usage

```bash
# Required Python packages
pip install pyyaml

# Make the script executable
chmod +x generate_argument_specs.py
```

**Requirements:**
- Python 3.6+
- PyYAML
- Ansible Core 2.11+ (for using the generated specs)

## Usage Modes

### Collection Mode (Default)

Process all roles in an Ansible collection automatically:

**Using pip installation (recommended):**
```bash
# Process all roles in current collection
ansible-argument-spec-generator

# Process all roles in specific collection path
ansible-argument-spec-generator --collection-path /path/to/collection

# List all roles found in collection
ansible-argument-spec-generator --list-roles

# Process only specific role in collection
ansible-argument-spec-generator --role snapshot_create
```

**Using direct script:**
```bash
# Process all roles in current collection
python generate_argument_specs.py

# Process all roles in specific collection path
python generate_argument_specs.py --collection-path /path/to/collection

# List all roles found in collection
python generate_argument_specs.py --list-roles

# Process only specific role in collection
python generate_argument_specs.py --role snapshot_create
```

### Single Role Mode

Process individual roles with more control:

**Using pip installation (recommended):**
```bash
# Interactive mode for single role
ansible-argument-spec-generator --single-role

# Generate from defaults file
ansible-argument-spec-generator --single-role --from-defaults defaults/main.yml

# Generate from configuration file
ansible-argument-spec-generator --single-role --from-config config.yml
```

**Using direct script:**
```bash
# Interactive mode for single role
python generate_argument_specs.py --single-role

# Generate from defaults file
python generate_argument_specs.py --single-role --from-defaults defaults/main.yml

# Generate from configuration file
python generate_argument_specs.py --single-role --from-config config.yml
```

### Verbosity Control

Control output detail level with verbosity flags:

**Using pip installation (recommended):**
```bash
# Silent mode (default) - only shows final summary
ansible-argument-spec-generator

# Basic processing info (-v)
ansible-argument-spec-generator -v

# Detailed processing information (-vv) 
ansible-argument-spec-generator -vv

# Full debug and trace output (-vvv)
ansible-argument-spec-generator -vvv
```

**Using direct script:**
```bash
# Silent mode (default) - only shows final summary
python generate_argument_specs.py

# Basic processing info (-v)
python generate_argument_specs.py -v

# Detailed processing information (-vv) 
python generate_argument_specs.py -vv

# Full debug and trace output (-vvv)
python generate_argument_specs.py -vvv

# Example output with different verbosity levels:

# No flags (silent):
# ============================================================
#   ARGUMENT SPECS GENERATION SUMMARY
# ============================================================
# Roles processed: 3
# Entry points created: 3
# Total variables: 24
# ============================================================

# With -v (basic info):
# Shows role processing steps and basic operations

# With -vv (detailed):
# Shows variable processing and file analysis details

# With -vvv (full debug):
# Shows complete trace of all operations and filtering
```

## Command Line Options

| Option | Mode | Description |
|--------|------|-------------|
| `--single-role` | Both | Enable single role mode (default: collection mode) |
| `--collection-path PATH` | Collection | Path to collection root (default: current directory) |
| `--list-roles` | Collection | List roles found in collection and exit |
| `--role NAME` | Collection | Process only the specified role |
| `--from-defaults FILE` | Single | Generate specs from defaults/main.yml file |
| `--from-config FILE` | Single | Generate from config file (YAML/JSON) |
| `--entry-point NAME` | Single | Entry point name for --from-defaults (default: main) |
| `--output FILE` | Single | Output file path (default: meta/argument_specs.yml) |
| `--validate-only` | Both | Only validate existing specs, don't generate |
| `--create-example-config` | Both | Create example configuration file |
| `-v, --verbose` | Both | Basic processing info for each role |
| `-vv` | Both | Detailed processing information |
| `-vvv` | Both | Full trace and debug information |

## Collection Mode Workflow

When run in collection mode (default), the script:

1. **Detects Collection**: Looks for `galaxy.yml` and `roles/` directory
2. **Finds Roles**: Scans `roles/` directory for valid role structures
3. **Analyzes Each Role**: 
   - Reads `defaults/main.yml` for variable definitions and type inference
   - Reads `vars/main.yml` for additional variables
   - Reads `meta/main.yml` for author and description information
   - Preserves existing `meta/argument_specs.yml` descriptions and customizations
   - Scans `tasks/` directory for entry points and variable usage
   - Extracts variables from task files, including those used in:
     - Assert statements (`assert`, `that` clauses)
     - Conditional statements (`when`, `failed_when`, `changed_when`)
     - Jinja2 templates and variable references
   - Determines file inclusion relationships and entry points
4. **Generates Specs**: Creates intelligent argument specs with:
   - Context-aware type inference (paths, URLs, states, etc.)
   - Smart descriptions based on variable naming patterns
   - Proper handling of nested variables from included files
5. **Saves Files**: Writes well-formatted `meta/argument_specs.yml` for each role

### Example Collection Structure

```
my_collection/
├── galaxy.yml
├── roles/
│   ├── webapp/
│   │   ├── defaults/main.yml
│   │   ├── tasks/main.yml
│   │   ├── tasks/install.yml
│   │   ├── tasks/configure.yml
│   │   └── meta/
│   │       └── argument_specs.yml  # Generated
│   └── database/
│       ├── defaults/main.yml
│       ├── tasks/main.yml
│       └── meta/
│           └── argument_specs.yml  # Generated
└── generate_argument_specs.py
```

### Collection Mode Output

```bash
$ python generate_argument_specs.py
Found 6 roles in collection: bigboot, initramfs, shrink_lv, snapshot_create, snapshot_remove, snapshot_revert

Processing role: bigboot
  Analyzing role structure...
    All task files found: main, install, configure
    All included files: install, configure
    Only 'main' entry point found
    Files included by others (not entry points): configure, install
      Variables found in main.yml: bigboot_enabled, grub_timeout
      Variables found in install.yml: boot_device_path
      Added variable from install.yml: boot_device_path
      Added variable from configure.yml: grub_config_path
  Creating specs for entry point: main
  Generated specs for 1 entry point(s)
  Found 3 default variables
  Saved argument specs to: roles/bigboot/meta/argument_specs.yml

Processing role: initramfs
  Analyzing role structure...
    All task files found: main, rebuild, backup
    All included files: rebuild
    Found standalone entry points: backup
    Files included by others (not entry points): rebuild
      Variables found in main.yml: initramfs_modules
      Variables found in backup.yml: backup_path, force_backup
  Creating specs for entry point: main
  Creating specs for entry point: backup
  Generated specs for 2 entry point(s)
  Found 2 default variables
  Saved argument specs to: roles/initramfs/meta/argument_specs.yml

...

✓ Successfully processed 6 role(s)
```

## Configuration File Format

For complex single-role scenarios, use a configuration file:

```yaml
entry_points:
  main:
    short_description: "Install and configure web application"
    description:
      - "Main entry point for application deployment"
      - "Includes installation, configuration, and service management"
    arguments:
      app_name:
        type: str
        required: true
        description: "Name of the application to deploy"
      
      state:
        type: str
        required: false
        default: "present"
        choices: ["present", "absent", "started", "stopped"]
        description: "Desired state of the application"
      
      app_port:
        type: int
        default: 8080
        description: "Port number for the application"
      
      config:
        type: dict
        description: "Application configuration dictionary"
      
      ssl_cert_path:
        type: path
        description: "Path to SSL certificate file"
      
      ssl_key_path:
        type: path
        description: "Path to SSL private key file"
    
    required_if:
      - ["state", "present", ["app_name"]]
    
    required_together:
      - ["ssl_cert_path", "ssl_key_path"]
  
  install:
    short_description: "Install application packages only"
    arguments:
      app_name:
        type: str
        required: true
        description: "Name of the application to install"
```

## Generated Output

The tool generates standard `argument_specs.yml` files:

```yaml
---
argument_specs:
  main:
    short_description: Auto-generated specs for webapp role - main entry point
    description:
      - Automatically generated argument specification for the webapp role.
      - "Entry point: main"
    author:
      - "John Doe <john@example.com>"
      - "Jane Smith <jane@example.com>"
    options:
      app_name:
        description: Name identifier
        type: str
        default: myapp
      app_version:
        description: Version specification
        type: str
        default: "1.0.0"
      app_enabled:
        description: Enable or disable functionality (boolean flag)
        type: bool
        default: true
      app_packages:
        description: List of values for app packages
        type: list
        elements: str
        default: []
        version_added: "1.1.0"
      config_path:
        description: File system path for config path
        type: path
        default: /etc/myapp/config.yml
        version_added: "1.2.0"
      debug_mode:
        description: Enable debug mode or output (boolean flag)
        type: bool
        default: false
...
```

## Enhanced Variable Detection

The tool now performs comprehensive analysis to detect variables used throughout your role:

### Task File Analysis

Variables are automatically extracted from:

- **Jinja2 Templates**: `{{ variable_name }}`, `{{ var | default('value') }}`
- **Conditional Statements**: `when: variable_name == 'value'`
- **Assert Statements**: 
  ```yaml
  assert:
    that:
      - variable_name is defined
      - other_var == "expected_value"
  ```
- **Failed/Changed When**: `failed_when: command_result.rc != 0`
- **Loop Variables**: `with_items: "{{ package_list }}"`

### Smart Type Inference

The enhanced type inference system:

- **Path Detection**: Variables named `*_path`, `*_dir`, `*_file` automatically get `type: path`
- **Boolean Flags**: Variables like `*_enabled`, `*_debug`, `force_*` get appropriate boolean descriptions
- **Network Settings**: Variables like `*_port`, `*_host`, `*_url` get context-aware descriptions

## Variable Filtering and Detection

The tool intelligently filters variables to include only legitimate role parameters:

### Automatic Variable Filtering

Variables are automatically excluded if they are:

- **Private/Internal Variables**: Starting with `__` (double underscore)
  ```yaml
  # These are filtered out:
  __tmp_version: "1.0.0"
  __internal_config: "secret"
  ```

- **Registered Variables**: Created with `register:` or `set_fact:`
  ```yaml
  # These are filtered out:
  - name: Run command
    command: /bin/true
    register: command_result  # ← Excluded
  
  - name: Set temporary fact
    set_fact:
      temp_result: "value"    # ← Excluded
  ```

- **Properties of Registered Variables**: Attributes like `.rc`, `.stdout`, `.stderr`
  ```yaml
  # If 'result' is registered, these are filtered out:
  when: result.rc == 0      # ← 'rc' excluded
  when: result.stdout       # ← 'stdout' excluded
  ```

- **Ansible Built-ins**: `ansible_facts`, `inventory_hostname`, `hostvars`, etc.

### Smart Required Field Detection

Variables are automatically marked as required based on their usage:

- **Variables WITHOUT defaults** → `required: true`
- **Variables WITH defaults** → `required: false` (optional)

```yaml
# Example: These variables have no defaults in defaults/main.yml
database_host:        # ← Marked as required: true
database_password:    # ← Marked as required: true

# These have defaults
app_name:            # ← Marked as required: false
  default: "myapp"
```

### Entry Point Processing

The tool processes variables from multiple sources:

- **Main Entry Point**: Variables used directly in `tasks/main.yml`
- **Included Task Files**: Variables from files included by entry points
- **Multiple Entry Points**: Supports roles with `install.yml`, `configure.yml`, etc.
- **Defaults and Vars**: Variables from `defaults/main.yml` and `vars/main.yml`

## Output Improvements

The tool generates clean, professional YAML output with several enhancements:

### Alphabetical Sorting

All options are automatically sorted alphabetically for consistent, readable specs:

```yaml
argument_specs:
  main:
    options:
      alpha_variable:           # ← Sorted A-Z
        description: "First variable"
      beta_variable:            # ← 
        description: "Second variable"
      zebra_variable:           # ← Last alphabetically
        description: "Last variable"
```

### Clean YAML Output

- **No Reference Anchors**: No more `description: *id001` - full content is repeated
- **Proper Document Markers**: Uses `---` and `...` for valid YAML documents
- **Consistent Formatting**: Proper indentation and spacing throughout
- **Unicode Support**: Handles international characters correctly

### Professional Structure

Generated files follow Ansible best practices:

```yaml
---
argument_specs:
  main:
    short_description: "Role short description"
    description:
      - "Detailed role description"
      - "Multi-line descriptions supported"
    author:
      - "Author Name <email@domain.com>"
    options:
      # Variables sorted alphabetically with full metadata
...
```

### Intelligent Descriptions

Generated descriptions are now context-aware:

```yaml
# Instead of generic descriptions:
timeout: "Auto-generated for timeout"

# You get meaningful descriptions:
timeout: "Timeout value in seconds (numeric value)"
debug_enabled: "Enable debug mode or output (boolean flag)"
config_path: "File system path for config path"
package_list: "List of values for package list"
```

## Advanced Features

### Multiple Entry Point Support

The tool automatically detects and processes multiple entry points in a role:

```yaml
# If your role has these task files:
tasks/
  ├── main.yml       # ← main entry point
  ├── install.yml    # ← install entry point
  └── configure.yml  # ← configure entry point

# Generated specs will include all entry points:
argument_specs:
  main:
    short_description: "Main role functionality"
    options: { ... }
  install:
    short_description: "Install packages only"
    options: { ... }
  configure:
    short_description: "Configure settings only"
    options: { ... }
```

### Comprehensive Error Recovery

The tool handles various edge cases gracefully:

- **Encoding Issues**: Automatically handles different file encodings
- **YAML Parse Errors**: Falls back to regex parsing when YAML fails
- **Missing Files**: Continues processing other files when some are missing
- **Complex Expressions**: Safely ignores unparseable Jinja2 expressions
- **File Access Errors**: Reports issues but continues with other files

### Debugging and Validation

Built-in debugging capabilities help troubleshoot issues:

```bash
# Progressive debugging levels
python generate_argument_specs.py -v      # Basic info
python generate_argument_specs.py -vv     # Detailed processing  
python generate_argument_specs.py -vvv    # Full trace output

# Validation only mode
python generate_argument_specs.py --validate-only

# List roles for verification
python generate_argument_specs.py --list-roles
```

## Description Priority System

The tool uses an intelligent priority system for descriptions and author information:

### Priority Order

1. **Existing Argument Specs** (Highest Priority)
   - Preserves manual edits in existing `meta/argument_specs.yml`
   - Ensures user customizations are never overwritten

2. **Meta Information** (Medium Priority)
   - Uses descriptions and author from `meta/main.yml`
   - Supports standard fields: `description`, `author`, `short_description`
   - Also checks `galaxy_info` nested fields

3. **Generated Content** (Lowest Priority)
   - Creates intelligent descriptions based on variable analysis
   - Only used when no existing or meta information is available

### Example Priority Flow

```yaml
# meta/main.yml
author: "John Doe <john@example.com>"
description: "A comprehensive web server role"
galaxy_info:
  short_description: "Installs and configures web server"

# Generated argument_specs.yml will use:
# - author: ["John Doe <john@example.com>"] (from meta/main.yml)
# - description: ["A comprehensive web server role"] (from meta/main.yml)
# - short_description: "Installs and configures web server" (from meta/main.yml)
```

### Console Output

The tool provides clear feedback about source priority:

```
Processing role: webapp
  Found 1 author(s): John Doe <john@example.com>
  Found description from meta/main.yml
  Creating specs for entry point: main
    Using description from meta/main.yml
    Using short_description from meta/main.yml
    Using author(s) from meta/main.yml: John Doe <john@example.com>
```

## Automatic Version Tracking

The tool automatically adds `version_added` fields to new argument specifications based on the current version:

### Version Detection Priority

1. **Collection Version** (Highest Priority)
   - Reads `galaxy.yml` version from collection root
   - Searches up to 3 directories from role location
   - Uses collection version for all roles in the collection

2. **Role Version** (Medium Priority)  
   - Uses `version` from `meta/main.yml` 
   - Also checks `galaxy_info.version` and `galaxy_info.role_version`
   - Applied when not part of a collection

3. **Default Version** (Fallback)
   - Uses `1.0.0` when no version information is found

### Smart Version Application

- **New Variables**: Variables not found in existing `argument_specs.yml` get `version_added` with current version
- **Existing Variables**: Variables already present in `argument_specs.yml` preserve their existing `version_added` field (or get none if they didn't have one)
- **Variables without version_added**: Existing variables that had no `version_added` field remain without one
- **Manual Specifications**: Honor user-specified version in config files and interactive mode

### Example Output

```yaml
# Collection version 2.1.0 detected
argument_specs:
  main:
    options:
      existing_var:
        description: "Previously defined variable" 
        type: str
        # No version_added (existed before)
      
      new_var:
        description: "Newly detected variable"
        type: str
        version_added: "2.1.0"  # Added automatically
      
      manual_var:
        description: "Manually configured variable"
        type: str
        version_added: "1.5.0"  # Preserved from existing specs
```

### Console Output

```
Processing role: webapp
  Detected version: 2.1.0 (collection)
  Loaded existing specs with 1 entry point(s)
  Creating specs for entry point: main
    Variable existing_var existed in argument specs - not adding version_added
    Adding version_added for new variable new_var: 2.1.0
    Using existing version_added for manual_var: 1.5.0
  Version tracking: 1 new variables, 2 existing variables
```

## Validation Features

The tool includes comprehensive validation:

**Using pip installation (recommended):**
```bash
# Validate all roles in collection
ansible-argument-spec-generator --validate-only

# Validate single role
ansible-argument-spec-generator --single-role --validate-only --output meta/argument_specs.yml
```

**Using direct script:**
```bash
# Validate all roles in collection
python generate_argument_specs.py --validate-only

# Validate single role
python generate_argument_specs.py --single-role --validate-only --output meta/argument_specs.yml
```

**Validation Checks:**
- Valid argument types
- Conditional requirements reference existing arguments
- Required fields are present
- Element types specified for lists/dicts
- No orphaned references

## Integration with Ansible

Once generated, the specs automatically:

1. **Provide Documentation**: `ansible-doc --type role my_collection.my_role`
2. **Validate Arguments**: Automatic validation before role execution
3. **Generate Error Messages**: Clear error messages for invalid inputs

### Example Usage

```yaml
- hosts: all
  roles:
    - name: my_collection.webapp
      app_name: "mysite"
      app_version: "2.0.0"
      state: "started"
```

If invalid arguments are provided:
```
TASK [my_collection.webapp : Validating arguments against arg specs] ****
fatal: [host]: FAILED! => {
  "argument_errors": [
    "value of state must be one of: present, absent, started, stopped. Got: invalid_state"
  ]
}
```

## Examples

### Example 1: Process Entire Collection

**Using pip installation (recommended):**
```bash
cd /path/to/my_collection
ansible-argument-spec-generator
```

**Using direct script:**
```bash
cd /path/to/my_collection
python generate_argument_specs.py
```

### Example 2: Process Single Role in Collection

**Using pip installation (recommended):**
```bash
cd /path/to/my_collection
ansible-argument-spec-generator --role webapp
```

**Using direct script:**
```bash
cd /path/to/my_collection
python generate_argument_specs.py --role webapp
```

### Example 3: Generate from Existing Defaults

**Using pip installation (recommended):**
```bash
cd /path/to/role
ansible-argument-spec-generator --single-role --from-defaults defaults/main.yml
```

**Using direct script:**
```bash
cd /path/to/role
python generate_argument_specs.py --single-role --from-defaults defaults/main.yml
```

### Example 4: Interactive Single Role

**Using pip installation (recommended):**
```bash
ansible-argument-spec-generator --single-role
```

**Using direct script:**
```bash
python generate_argument_specs.py --single-role
```

Interactive prompts guide you through creating comprehensive specs.

## Best Practices

1. **Collection Mode**: Use for consistent specs across all roles
2. **Regular Updates**: Re-run when role variables change
3. **Version Control**: Commit generated specs to track changes
4. **Validation**: Always validate before committing
5. **Documentation**: Review generated descriptions and improve them
6. **Testing**: Test generated specs with actual role usage

## Troubleshooting

### Enhanced Error Handling

The tool now provides detailed error messages for common issues:

- **File Encoding Issues**: Automatically detects and reports UTF-8 encoding problems
- **YAML Syntax Errors**: Specific error messages for malformed YAML files  
- **Missing Files**: Clear messages when expected files don't exist
- **Empty Files**: Graceful handling of empty defaults/vars files
- **Permission Issues**: Detailed reporting of file access problems

### Common Issues

1. **"Not a collection root"**
   ```bash
   # Ensure you're in the collection root with galaxy.yml and roles/
   ls -la  # Should show galaxy.yml and roles/
   ```

2. **"No roles found"**
   ```bash
   # Check roles directory structure
   ls -la roles/  # Should show role directories
   python generate_argument_specs.py --list-roles
   ```

3. **YAML parsing errors**
   ```bash
   # The tool now provides specific YAML error details:
   # Error: Invalid YAML in roles/myrole/defaults/main.yml: mapping values are not allowed here
   
   # Check syntax manually if needed:
   python -c "import yaml; yaml.safe_load(open('roles/myrole/defaults/main.yml'))"
   ```

4. **File encoding issues**
   ```bash
   # Error: Could not decode file roles/myrole/tasks/main.yml: 'utf-8' codec can't decode
   # Convert file to UTF-8 encoding
   iconv -f iso-8859-1 -t utf-8 roles/myrole/tasks/main.yml > temp && mv temp roles/myrole/tasks/main.yml
   ```

### Debugging

**Using pip installation (recommended):**
```bash
# List roles in collection
ansible-argument-spec-generator --list-roles

# Validate existing specs
ansible-argument-spec-generator --validate-only

# Process single role for testing
ansible-argument-spec-generator --role myrole

# Progressive verbosity for troubleshooting
ansible-argument-spec-generator -v        # Basic processing info
ansible-argument-spec-generator -vv       # Detailed variable processing
ansible-argument-spec-generator -vvv      # Full debug trace

# Debug variable filtering (shows what's excluded)
ansible-argument-spec-generator -vvv --role myrole | grep -E "(Excluding|Variables found)"

# Check entry point detection
ansible-argument-spec-generator -vv --role myrole | grep -E "(entry point|Entry Point)"
```

**Using direct script:**
```bash
# List roles in collection
python generate_argument_specs.py --list-roles

# Validate existing specs
python generate_argument_specs.py --validate-only

# Process single role for testing
python generate_argument_specs.py --role myrole

# Progressive verbosity for troubleshooting
python generate_argument_specs.py -v        # Basic processing info
python generate_argument_specs.py -vv       # Detailed variable processing
python generate_argument_specs.py -vvv      # Full debug trace

# Debug variable filtering (shows what's excluded)
python generate_argument_specs.py -vvv --role myrole | grep -E "(Excluding|Variables found)"

# Check entry point detection
python generate_argument_specs.py -vv --role myrole | grep -E "(entry point|Entry Point)"
```

## Package Distribution

### Publishing to PyPI

This package uses GitHub Actions for automated publishing to PyPI. The workflow is triggered in two ways:

#### Automatic Release Publishing
When you create a new release on GitHub:
1. Create a new tag: `git tag v1.0.0`
2. Push the tag: `git push origin v1.0.0` 
3. Create a release on GitHub using that tag
4. The package will automatically be built and published to PyPI

#### Manual Test Publishing
To test publishing without a release:
1. Go to the "Actions" tab in GitHub
2. Select "Publish to PyPI"
3. Click "Run workflow"
4. Check "Publish to Test PyPI instead of PyPI"
5. The package will be published to Test PyPI for testing

### Installation from PyPI

Once published, users can install directly from PyPI:

```bash
# Install from PyPI (when published)
pip install ansible-argument-spec-generator

# Install from Test PyPI (for testing)
pip install --index-url https://test.pypi.org/simple/ ansible-argument-spec-generator
```

### Development Installation

For development and local testing:

```bash
# Clone the repository
git clone https://github.com/yourusername/ansible-argument-spec-generator.git
cd ansible-argument-spec-generator

# Install in development mode
pip install -e .
```

## Contributing

We welcome contributions! This project has comprehensive testing and CI/CD infrastructure to ensure quality.

### Quick Start for Contributors

1. **Fork and clone the repository**
2. **Set up development environment:**
   ```bash
   # Install in development mode with test dependencies
   pip install -e ".[dev]"
   ```

3. **Run tests before making changes:**
   ```bash
   # Quick status check
   python scripts/test-status.py --quick
   
   # Full test suite
   python scripts/test-status.py
   ```

4. **Make your changes and test thoroughly**
5. **Submit a pull request**

### Testing Requirements

This project maintains **high testing standards**:

- ✅ **80%+ test coverage** required
- ✅ **Comprehensive test suite** with 150+ tests
- ✅ **Multiple test categories:** unit, integration, edge cases
- ✅ **Automated CI/CD** testing on multiple Python versions

#### Running Tests

**Basic smoke tests (quick):**
```bash
python tests/test_runner.py --basic
```

**Full test suite:**
```bash
# Using pytest (recommended)
pytest tests/ -v

# Using custom runner  
python tests/test_runner.py

# With coverage report
pytest tests/ --cov=generate_argument_specs --cov-report=html
```

**Test specific areas:**
```bash
pytest tests/test_basic.py -v                    # Smoke tests
pytest tests/test_integration.py -v              # Integration tests
pytest tests/test_edge_cases.py -v               # Edge cases
```

**Check test completeness:**
```bash
python .github/scripts/check_test_completeness.py
```

### Development Guidelines

#### Code Quality
- **Format code:** `black .`
- **Lint code:** `flake8 generate_argument_specs.py tests/`
- **Type checking:** `mypy generate_argument_specs.py`
- **Test locally** before pushing

#### Adding New Features
1. **Write tests first** (TDD approach recommended)
2. **Add both unit and integration tests**
3. **Test error conditions** and edge cases
4. **Update documentation** if needed
5. **Ensure all tests pass**

#### Test Categories
When adding tests, consider these categories:

- **Unit tests** - Individual functions/classes
- **Integration tests** - Complete workflows  
- **Edge cases** - Error handling, malformed input
- **Performance tests** - Large files, many roles
- **CLI tests** - Command-line interface

### Pull Request Process

1. **Create feature branch** from `main`
2. **Make changes** with comprehensive tests
3. **Run full test suite** locally
4. **Submit PR** with clear description
5. **Address review feedback**

#### PR Requirements
- ✅ All tests pass
- ✅ Test coverage maintained/improved
- ✅ Code formatting (black)
- ✅ No linting errors
- ✅ Documentation updated if needed

#### Automated Checks
Every PR automatically runs:
- **Test suite** on Python 3.8-3.12
- **Test completeness** verification
- **Code quality** checks (black, flake8, mypy)
- **Installation testing** 
- **Integration testing**

### Local Development Tools

**Quick status check:**
```bash
python scripts/test-status.py --quick
```

**Full status check:**
```bash
python scripts/test-status.py
```

**Test specific functionality:**
```bash
# Test collection mode
cd test_collection && ansible-argument-spec-generator -v

# Test single role mode  
cd test_role && ansible-argument-spec-generator --single-role -v
```

### Getting Help

- 📖 **Read the tests:** `tests/README.md` has detailed testing documentation
- 🐛 **Report bugs:** Use GitHub issues with full details
- 💡 **Suggest features:** Open an issue for discussion first
- 🤝 **Ask questions:** GitHub discussions or issues

### Code Standards

- **Python 3.8+** compatibility
- **Type hints** for new code
- **Docstrings** for public methods
- **Clear variable names**
- **Comprehensive error handling**
- **Follow existing patterns**

### Testing Philosophy

This project follows **comprehensive testing** principles:

- **Every function should have tests**
- **Edge cases and errors must be tested**
- **Integration tests verify real-world usage**
- **Performance considerations for large inputs**
- **Backward compatibility preservation**

Thank you for contributing to make Ansible argument specs generation better! 🚀

## License

MIT
