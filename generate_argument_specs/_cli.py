"""
Command-line interface for the argument spec generator.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

from ._exceptions import (
    CollectionNotFoundError,
    ConfigError,
    GeneratorError,
    RoleNotFoundError,
    ValidationError,
)
from ._generator import ArgumentSpecsGenerator
from ._models import ArgumentSpec, EntryPointSpec

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("ansible-argument-spec-generator")
except Exception:
    __version__ = "1.1.0"


def create_example_config():
    """Create an example configuration file"""
    example_config = {
        "entry_points": {
            "main": {
                "short_description": "Main entry point for the role",
                "description": [
                    "This is the main entry point that combines all functionality.",
                    "It handles the primary workflow of the role.",
                ],
                "author": [
                    "Your Name <your.email@example.com>",
                    "Another Author <author@example.com>",
                ],
                "arguments": {
                    "state": {
                        "type": "str",
                        "required": False,
                        "default": "present",
                        "choices": ["present", "absent"],
                        "description": "Desired state of the resource",
                    },
                    "name": {
                        "type": "str",
                        "required": True,
                        "description": "Name of the resource to manage",
                    },
                    "config": {
                        "type": "dict",
                        "required": False,
                        "description": "Configuration dictionary for the resource",
                        "version_added": "1.1.0",
                    },
                    "items": {
                        "type": "list",
                        "elements": "str",
                        "default": [],
                        "description": "List of items to process",
                        "version_added": "1.2.0",
                    },
                },
                "mutually_exclusive": [["config", "items"]],
                "required_if": [["state", "present", ["name"]]],
            }
        }
    }

    yaml_content = yaml.dump(
        example_config, default_flow_style=False, sort_keys=False, indent=2
    )

    lines = yaml_content.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not (stripped.startswith("&") and len(stripped.split()) == 1) and not (
            stripped.startswith("*") and len(stripped.split()) == 1
        ):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _print_unless_quiet(msg: str, quiet: bool = False):
    """Print a message unless quiet mode is enabled."""
    if not quiet:
        print(msg)


def main():  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Generate Ansible argument_specs.yml files for collections or individual roles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collection mode (default) - process all roles in collection
  generate-argument-spec

  # Single role mode - interactive mode for one role
  generate-argument-spec --single-role

  # Single role mode - generate from defaults file
  generate-argument-spec --single-role --from-defaults defaults/main.yml

  # Collection mode - specify collection path
  generate-argument-spec --collection-path /path/to/collection

  # Generate from config file (single role)
  generate-argument-spec --single-role --from-config config.yml

  # Create example config
  generate-argument-spec --create-example-config

  # Use verbosity for debugging
  generate-argument-spec -vv  # Show variable processing details

  # Dry run (preview without writing files)
  generate-argument-spec --dry-run

  # Suppress all output
  generate-argument-spec --quiet
        """,
    )

    parser.add_argument(
        "--single-role",
        action="store_true",
        help="Run in single role mode (default: collection mode)",
    )

    parser.add_argument(
        "--collection-path",
        default=".",
        help="Path to collection root (default: current directory)",
    )

    parser.add_argument(
        "--from-defaults",
        metavar="FILE",
        help="Generate specs from a defaults/main.yml file (single role mode only)",
    )

    parser.add_argument(
        "--from-config",
        metavar="FILE",
        help="Generate specs from a configuration file (single role mode only)",
    )

    parser.add_argument(
        "--entry-point",
        default="main",
        help="Entry point name when using --from-defaults (default: main)",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: meta/argument_specs.yml for single role, auto for collection)",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing specs, don't generate new ones",
    )

    parser.add_argument(
        "--create-example-config",
        action="store_true",
        help="Create an example configuration file",
    )

    parser.add_argument(
        "--list-roles",
        action="store_true",
        help="List roles found in collection and exit",
    )

    parser.add_argument(
        "--role", help="Process only the specified role in collection mode"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be generated without writing files",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all output (useful in CI pipelines)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="""Increase verbosity levels:
  (none): Only show final summary
  -v: Show basic processing info for each role  
  -vv: Show detailed processing information
  -vvv: Show full trace and debug information""",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    quiet = args.quiet
    if quiet:
        args.verbose = -1

    if args.create_example_config:
        example_content = create_example_config()
        with open("example_config.yml", "w") as f:
            f.write(example_content)
        _print_unless_quiet("Example configuration saved to: example_config.yml", quiet)
        return

    collection_mode = not args.single_role

    if not collection_mode:
        if args.list_roles:
            parser.error("--list-roles is only available in collection mode")
        if args.role:
            parser.error("--role is only available in collection mode")
    else:
        if args.from_defaults:
            parser.error("--from-defaults is only available in single role mode")
        if args.from_config:
            parser.error("--from-config is only available in single role mode")

    generator = ArgumentSpecsGenerator(
        collection_mode=collection_mode,
        verbosity=args.verbose,
        dry_run=args.dry_run,
    )

    try:
        if collection_mode:
            _main_collection_mode(args, generator, quiet)
        else:
            _main_single_role_mode(args, generator, quiet)
    except GeneratorError as e:
        _print_unless_quiet(f"Error: {e}", quiet)
        sys.exit(1)
    except KeyboardInterrupt:
        _print_unless_quiet("\nInterrupted.", quiet)
        sys.exit(130)
    except Exception as e:
        _print_unless_quiet(f"Unexpected error: {e}", quiet)
        sys.exit(1)


def _main_collection_mode(args, generator, quiet):
    """Handle collection mode logic."""
    if args.list_roles:
        if generator.is_collection_root(args.collection_path):
            roles = generator.find_roles(args.collection_path)
            if roles:
                _print_unless_quiet(f"Found {len(roles)} roles in collection:", quiet)
                for role in roles:
                    _print_unless_quiet(f"  - {role}", quiet)
            else:
                _print_unless_quiet("No roles found in collection", quiet)
        else:
            raise CollectionNotFoundError(
                f"{args.collection_path} is not a collection root"
            )
        return

    if args.validate_only:
        _validate_collection(args, generator, quiet)
        return

    if args.role:
        role_path = Path(args.collection_path) / "roles" / args.role
        if not role_path.exists():
            raise RoleNotFoundError(f"Role '{args.role}' not found in collection")
        generator.process_single_role(str(role_path), args.role)
        generator.processed_roles.append(args.role)
    else:
        generator.process_collection(args.collection_path)

    _print_unless_quiet(
        f"\n✓ Successfully processed {len(generator.processed_roles)} role(s)", quiet
    )


def _validate_collection(args, generator, quiet):
    """Validate all existing specs in a collection."""
    roles = generator.find_roles(args.collection_path)
    for role_name in roles:
        role_path = Path(args.collection_path) / "roles" / role_name
        specs_file = role_path / "meta" / "argument_specs.yml"
        if specs_file.exists():
            _print_unless_quiet(f"Validating {role_name}...", quiet)
            with open(specs_file, "r") as f:
                existing_specs = yaml.safe_load(f)

            generator.entry_points.clear()
            for entry_name, entry_data in existing_specs.get(
                "argument_specs", {}
            ).items():
                entry_point = EntryPointSpec(name=entry_name)
                entry_point.short_description = entry_data.get("short_description", "")
                entry_point.description = entry_data.get("description", [])

                for arg_name, arg_data in entry_data.get("options", {}).items():
                    arg_spec = ArgumentSpec(
                        name=arg_name,
                        type=arg_data.get("type", "str"),
                        required=arg_data.get("required", False),
                        default=arg_data.get("default"),
                        choices=arg_data.get("choices"),
                        description=arg_data.get("description"),
                        elements=arg_data.get("elements"),
                    )
                    entry_point.options[arg_name] = arg_spec

                generator.add_entry_point(entry_point)

            if not generator.validate_specs():
                raise ValidationError(f"Validation failed for {role_name}")
            else:
                _print_unless_quiet(f"✓ {role_name} specs are valid", quiet)

    _print_unless_quiet("✓ All collection specs are valid", quiet)


def _main_single_role_mode(args, generator, quiet):
    """Handle single role mode logic."""
    if args.validate_only:
        output_file = args.output or "meta/argument_specs.yml"
        if not os.path.exists(output_file):
            raise ConfigError(f"No existing specs found at {output_file}")

        with open(output_file, "r") as f:
            existing_specs = yaml.safe_load(f)

        for entry_name, entry_data in existing_specs.get("argument_specs", {}).items():
            entry_point = EntryPointSpec(name=entry_name)
            entry_point.short_description = entry_data.get("short_description", "")
            entry_point.description = entry_data.get("description", [])

            for arg_name, arg_data in entry_data.get("options", {}).items():
                arg_spec = ArgumentSpec(
                    name=arg_name,
                    type=arg_data.get("type", "str"),
                    required=arg_data.get("required", False),
                    default=arg_data.get("default"),
                    choices=arg_data.get("choices"),
                    description=arg_data.get("description"),
                    elements=arg_data.get("elements"),
                )
                entry_point.options[arg_name] = arg_spec

            generator.add_entry_point(entry_point)
    else:
        if args.from_defaults:
            generator.from_defaults_file(args.from_defaults, args.entry_point)
        elif args.from_config:
            generator.from_config_file(args.from_config)
        else:
            generator.interactive_mode()

    if generator.entry_points:
        if generator.validate_specs():
            _print_unless_quiet("✓ All specs are valid", quiet)

            if not args.validate_only:
                output_file = args.output or "meta/argument_specs.yml"
                if args.dry_run:
                    yaml_content = generator.generate_yaml()
                    _print_unless_quiet(
                        f"\n--- Dry run: would write to {output_file} ---", quiet
                    )
                    _print_unless_quiet(yaml_content, quiet)
                else:
                    generator.save_to_file(output_file)
                    _print_unless_quiet(
                        f"\nGenerated argument_specs.yml with "
                        f"{len(generator.entry_points)} entry point(s)",
                        quiet,
                    )
        else:
            raise ValidationError("Validation failed")
    else:
        _print_unless_quiet("No entry points generated", quiet)
