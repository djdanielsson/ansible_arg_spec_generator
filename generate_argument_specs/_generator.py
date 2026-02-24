"""
Core ArgumentSpecsGenerator class that orchestrates spec generation.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from ._exceptions import (
    CollectionNotFoundError,
    ConfigError,
    RoleNotFoundError,
    ValidationError,
)
from ._models import ArgumentSpec, ArgumentType, EntryPointSpec
from ._type_inference import TypeInferenceMixin
from ._variable_extraction import VariableExtractionMixin
from ._yaml_output import YamlOutputMixin


class ArgumentSpecsGenerator(
    VariableExtractionMixin,
    TypeInferenceMixin,
    YamlOutputMixin,
):
    """Main class for generating argument specs"""

    def __init__(
        self,
        collection_mode: bool = True,
        verbosity: int = 0,
        dry_run: bool = False,
    ):
        self.entry_points: Dict[str, EntryPointSpec] = {}
        self.collection_mode = collection_mode
        self.processed_roles: List[str] = []
        self.variable_context: Dict[str, Dict[str, Any]] = {}
        self.verbosity = verbosity
        self.dry_run = dry_run
        self.current_role = ""
        self.stats = {
            "roles_processed": 0,
            "roles_failed": 0,
            "total_variables": 0,
            "new_variables": 0,
            "existing_variables": 0,
            "entry_points_created": 0,
        }

    def add_entry_point(self, entry_point: EntryPointSpec):
        """Add an entry point to the specification"""
        self.entry_points[entry_point.name] = entry_point

    # ------------------------------------------------------------------ logging

    def log(self, level: int, message: str, role_prefix: bool = True):
        """Log a message if verbosity level is sufficient"""
        if self.verbosity >= level:
            prefix = (
                f"[{self.current_role}] " if role_prefix and self.current_role else ""
            )
            print(f"{prefix}{message}")

    def log_info(self, message: str, role_prefix: bool = True):
        """Log info level message (verbosity >= 1)"""
        self.log(1, message, role_prefix)

    def log_verbose(self, message: str, role_prefix: bool = True):
        """Log verbose message (verbosity >= 2)"""
        self.log(2, f"  {message}", role_prefix)

    def log_debug(self, message: str, role_prefix: bool = True):
        """Log debug message (verbosity >= 3)"""
        self.log(3, f"    {message}", role_prefix)

    def log_trace(self, message: str, role_prefix: bool = True):
        """Log trace message (verbosity >= 3)"""
        self.log(3, f"      {message}", role_prefix)

    def log_error(self, message: str, role_prefix: bool = True):
        """Log error message (always shown regardless of verbosity)"""
        prefix = f"[{self.current_role}] " if role_prefix and self.current_role else ""
        print(f"{prefix}{message}")

    def log_section(self, title: str):
        """Log a section header"""
        if self.verbosity >= 1:
            print(f"\n{'='*60}")
            print(f"  {title}")
            print("=" * 60)

    def log_summary(self):
        """Log final summary"""
        print(f"\n{'='*60}")
        print("  ARGUMENT SPECS GENERATION SUMMARY")
        print("=" * 60)
        print(f"Roles processed: {self.stats['roles_processed']}")
        if self.stats["roles_failed"] > 0:
            print(f"Roles failed: {self.stats['roles_failed']}")
        print(f"Entry points created: {self.stats['entry_points_created']}")
        print(f"Total variables: {self.stats['total_variables']}")
        print(f"  - New variables: {self.stats['new_variables']}")
        print(f"  - Existing variables: {self.stats['existing_variables']}")

        if self.processed_roles:
            print(f"\nProcessed roles: {', '.join(self.processed_roles)}")

        print("=" * 60)

    # ------------------------------------------------------------------ helpers

    def _safe_load_yaml_file(
        self, file_path: Path, description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Safely load a YAML file with proper error handling"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return {}
                return yaml.safe_load(content)
        except yaml.YAMLError as e:
            self.log_error(f"Invalid YAML in {file_path}: {e}")
            return None
        except (OSError, IOError) as e:
            self.log_error(f"Could not read {file_path}: {e}")
            return None
        except Exception as e:
            self.log_verbose(f"Could not parse {file_path}: {e}")
            return None

    def is_collection_root(self, path: str = ".") -> bool:
        """Check if the current directory is a collection root"""
        path_obj = Path(path)
        has_roles = (path_obj / "roles").is_dir()
        has_galaxy = (path_obj / "galaxy.yml").is_file()

        return has_roles and (
            has_galaxy or len(list((path_obj / "roles").iterdir())) > 0
        )

    def find_roles(self, collection_path: str = ".") -> List[str]:
        """Find all roles in the collection"""
        roles_dir = Path(collection_path) / "roles"
        if not roles_dir.exists():
            return []

        roles = []
        for item in roles_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                role_indicators = [
                    "tasks/",
                    "defaults/",
                    "meta/",
                    "handlers/",
                    "templates/",
                    "files/",
                ]
                if any((item / indicator).exists() for indicator in role_indicators):
                    roles.append(item.name)

        return sorted(roles)

    # ---------------------------------------------------- role structure analysis

    def analyze_role_structure(self, role_path: str) -> Dict[str, Any]:
        """Analyze a role's structure to understand its arguments"""
        role_dir = Path(role_path)

        if not role_dir.exists():
            raise FileNotFoundError(f"Role path does not exist: {role_path}")

        if not role_dir.is_dir():
            raise NotADirectoryError(f"Role path is not a directory: {role_path}")

        analysis = {
            "defaults": {},
            "vars": {},
            "task_vars": set(),
            "template_vars": set(),
            "variables": {},
            "has_entry_points": False,
            "entry_points": {
                "main": {
                    "variables": {},
                    "description": "",
                    "short_description": "",
                }
            },
            "included_files": set(),
            "all_task_files": set(),
            "file_variables": {},
            "authors": [],
            "meta_description": [],
            "meta_short_description": "",
            "meta_info": {},
            "version_info": {},
            "version": "1.0.0",
            "is_collection": False,
        }

        version_info = self._detect_version_info(role_dir)
        analysis["version"] = version_info["version"]
        analysis["is_collection"] = version_info["is_collection"]
        analysis["version_info"] = version_info
        if version_info["version"] != "1.0.0":
            self.log_debug(
                f"Detected version: {version_info['version']} ({'collection' if version_info['is_collection'] else 'role'})"
            )
        else:
            self.log_trace(f"Using default version: {version_info['version']}")

        # Analyze defaults/main.yml
        defaults_file = role_dir / "defaults" / "main.yml"
        if defaults_file.exists():
            defaults = self._safe_load_yaml_file(defaults_file)
            if defaults is not None:
                analysis["defaults"] = defaults if isinstance(defaults, dict) else {}
            else:
                analysis["defaults"] = {}

        # Analyze vars/main.yml
        vars_file = role_dir / "vars" / "main.yml"
        if vars_file.exists():
            vars_data = self._safe_load_yaml_file(vars_file)
            if vars_data is not None:
                analysis["vars"] = vars_data if isinstance(vars_data, dict) else {}
            else:
                analysis["vars"] = {}

        # Analyze meta/main.yml for author information
        meta_file = role_dir / "meta" / "main.yml"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        meta_data = yaml.safe_load(content)
                        if isinstance(meta_data, dict):
                            authors = self._extract_authors_from_meta(meta_data)
                            analysis["authors"] = authors
                            if authors:
                                self.log_verbose(
                                    f"Found {len(authors)} author(s): {', '.join(authors)}"
                                )

                            descriptions = self._extract_descriptions_from_meta(
                                meta_data
                            )
                            analysis["meta_description"] = descriptions.get(
                                "description", []
                            )
                            analysis["meta_short_description"] = descriptions.get(
                                "short_description", ""
                            )
                            if descriptions.get("description") or descriptions.get(
                                "short_description"
                            ):
                                self.log_verbose(
                                    f"Found description from meta/main.yml"
                                )
                    else:
                        analysis["authors"] = []
                        analysis["meta_description"] = []
                        analysis["meta_short_description"] = ""
            except yaml.YAMLError as e:
                self.log_verbose(f"Invalid YAML in {meta_file}: {e}")
                analysis["authors"] = []
                analysis["meta_description"] = []
                analysis["meta_short_description"] = ""
            except (OSError, IOError) as e:
                self.log_verbose(f"Could not read {meta_file}: {e}")
                analysis["authors"] = []
                analysis["meta_description"] = []
                analysis["meta_short_description"] = ""
            except Exception as e:
                self.log_verbose(f"Could not parse {meta_file}: {e}")
                analysis["authors"] = []
                analysis["meta_description"] = []
                analysis["meta_short_description"] = ""

        # Analyze task files
        self._analyze_task_files(role_dir, analysis)

        # Populate fields expected by tests
        analysis["meta_info"] = {
            "authors": analysis["authors"],
            "description": analysis["meta_description"],
            "short_description": analysis["meta_short_description"],
        }

        # Combine all variables into the 'variables' field expected by tests (as dict)
        all_variables = {}

        if analysis.get("defaults"):
            for var_name, default_value in analysis["defaults"].items():
                all_variables[var_name] = {
                    "type": "str",
                    "default": default_value,
                    "required": False,
                    "description": f"Variable from defaults: {var_name}",
                }

        if analysis.get("vars"):
            for var_name, var_value in analysis["vars"].items():
                if var_name not in all_variables:
                    all_variables[var_name] = {
                        "type": "str",
                        "required": True,
                        "description": f"Variable from vars: {var_name}",
                    }

        for var_name in analysis.get("task_vars", set()):
            if var_name not in all_variables:
                all_variables[var_name] = {
                    "type": "str",
                    "required": True,
                    "description": f"Variable used in tasks: {var_name}",
                }

        for var_name in analysis.get("template_vars", set()):
            if var_name not in all_variables:
                all_variables[var_name] = {
                    "type": "str",
                    "required": True,
                    "description": f"Variable used in templates: {var_name}",
                }

        analysis["variables"] = all_variables

        analysis["entry_points"]["main"]["variables"] = all_variables.copy()

        return analysis

    def _detect_version_info(self, role_dir: Path) -> Dict[str, Any]:
        """Detect version information from collection or role metadata"""
        version_info = {"version": "1.0.0", "is_collection": False, "source": "default"}

        current_dir = role_dir
        collection_root = None

        for _ in range(3):
            current_dir = current_dir.parent
            galaxy_file = current_dir / "galaxy.yml"
            if galaxy_file.exists():
                collection_root = current_dir
                break

        if collection_root:
            try:
                with open(collection_root / "galaxy.yml", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        galaxy_data = yaml.safe_load(content)
                        if isinstance(galaxy_data, dict) and "version" in galaxy_data:
                            version_info["version"] = str(galaxy_data["version"])
                            version_info["is_collection"] = True
                            version_info["source"] = "collection"
                            return version_info
            except Exception as e:
                self.log_verbose(f"Could not parse galaxy.yml: {e}")

        meta_file = role_dir / "meta" / "main.yml"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        meta_data = yaml.safe_load(content)
                        if isinstance(meta_data, dict):
                            version_fields = [
                                "version",
                                "galaxy_info.version",
                                "galaxy_info.role_version",
                            ]

                            for field in version_fields:
                                version = self._get_nested_value(meta_data, field)
                                if version:
                                    version_info["version"] = str(version)
                                    version_info["is_collection"] = False
                                    version_info["source"] = "role"
                                    return version_info
            except Exception as e:
                self.log_verbose(f"Could not parse meta/main.yml for version: {e}")

        return version_info

    def _extract_authors_from_meta(self, meta_data: Dict[str, Any]) -> List[str]:
        """Extract author information from meta/main.yml data"""
        authors = []

        author_fields = [
            "author",
            "authors",
            "galaxy_info.author",
            "galaxy_info.authors",
        ]

        for field in author_fields:
            value = self._get_nested_value(meta_data, field)
            if value:
                if isinstance(value, str):
                    authors.append(value.strip())
                elif isinstance(value, list):
                    for author in value:
                        if isinstance(author, str) and author.strip():
                            authors.append(author.strip())
                break

        unique_authors = []
        for author in authors:
            if author not in unique_authors:
                unique_authors.append(author)

        return unique_authors

    def _extract_descriptions_from_meta(
        self, meta_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract description information from meta/main.yml data"""
        descriptions = {"description": [], "short_description": ""}

        description_fields = [
            "description",
            "galaxy_info.description",
            "galaxy_info.role_description",
        ]

        short_description_fields = [
            "short_description",
            "galaxy_info.short_description",
            "galaxy_info.summary",
        ]

        for field in description_fields:
            value = self._get_nested_value(meta_data, field)
            if value:
                if isinstance(value, str):
                    descriptions["description"] = value.strip()
                elif isinstance(value, list):
                    desc_lines = []
                    for line in value:
                        if isinstance(line, str) and line.strip():
                            desc_lines.append(line.strip())
                    descriptions["description"] = desc_lines
                break

        for field in short_description_fields:
            value = self._get_nested_value(meta_data, field)
            if value and isinstance(value, str):
                descriptions["short_description"] = value.strip()
                break

        return descriptions

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get a nested value from a dictionary using dot notation"""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _analyze_task_files(self, role_dir: Path, analysis: Dict[str, Any]):
        """Analyze task files to find variables and entry points"""
        tasks_dir = role_dir / "tasks"
        if not tasks_dir.exists():
            return

        task_files = list(tasks_dir.glob("*.yml")) + list(tasks_dir.glob("*.yaml"))
        all_included_files = set()
        file_includes_map = {}

        for task_file in task_files:
            analysis["all_task_files"].add(task_file.stem)

        for task_file in task_files:
            includes = self.parse_task_file_includes(task_file)
            variables = self.extract_variables_from_task_file(task_file)

            all_included_files.update(includes)
            file_includes_map[task_file.stem] = includes
            analysis["file_variables"][task_file.stem] = variables

            if includes:
                self.log_debug(
                    f"{task_file.stem} includes: {', '.join(sorted(includes))}"
                )

        self.log_debug(
            f"All task files found: {', '.join(sorted([f.stem for f in task_files]))}"
        )
        self.log_debug(
            f"All included files: {', '.join(sorted(all_included_files)) if all_included_files else 'None'}"
        )

        analysis["included_files"] = all_included_files
        analysis["file_includes_map"] = file_includes_map

        self._determine_entry_points(task_files, all_included_files, analysis)

    def _determine_entry_points(
        self, task_files: List[Path], all_included_files: set, analysis: Dict[str, Any]
    ):
        """Determine which task files are entry points"""
        standalone_files = set()
        for task_file in task_files:
            if task_file.stem != "main" and task_file.stem not in all_included_files:
                standalone_files.add(task_file.stem)

        if "main" not in analysis["entry_points"]:
            analysis["entry_points"]["main"] = {
                "variables": {},
                "description": "",
                "short_description": "",
            }

        if standalone_files:
            for file_name in sorted(standalone_files):
                if file_name not in analysis["entry_points"]:
                    analysis["entry_points"][file_name] = {
                        "variables": {},
                        "description": f"Entry point for {file_name}",
                        "short_description": f"Standalone task file: {file_name}",
                    }
            analysis["has_entry_points"] = True
            self.log_debug(
                f"Found standalone entry points: {', '.join(sorted(standalone_files))}"
            )
            if all_included_files:
                self.log_debug(
                    f"Files included by others (not entry points): {', '.join(sorted(all_included_files))}"
                )
        else:
            self.log_debug(f"Only 'main' entry point found")
            if all_included_files:
                self.log_debug(
                    f"All other files are included: {', '.join(sorted(all_included_files))}"
                )

    # -------------------------------------------- collection / role processing

    def process_collection(self, collection_path: str = "."):
        """Process all roles in a collection"""
        self.log_section("PROCESSING ANSIBLE COLLECTION")

        if not self.is_collection_root(collection_path):
            raise CollectionNotFoundError(
                f"{collection_path} does not appear to be an Ansible collection root. "
                "Expected to find a 'roles/' directory and preferably 'galaxy.yml'"
            )

        roles = self.find_roles(collection_path)
        if not roles:
            raise CollectionNotFoundError(f"No roles found in {collection_path}/roles/")

        self.log_info(
            f"Found {len(roles)} roles in collection: {', '.join(roles)}", False
        )

        for role_name in roles:
            self.current_role = role_name
            self.log_info(f"Processing role: {role_name}", False)
            role_path = Path(collection_path) / "roles" / role_name

            try:
                self.process_single_role(str(role_path), role_name)
                self.processed_roles.append(role_name)
                self.stats["roles_processed"] += 1
            except Exception as e:
                self.log_error(f"Error processing role {role_name}: {e}", False)
                self.stats["roles_failed"] += 1
                continue

        self.current_role = ""
        self.log_summary()

    def _merge_included_variables(
        self,
        entry_point: EntryPointSpec,
        entry_point_name: str,
        analysis: Dict[str, Any],
        existing_options: Dict[str, Dict[str, Any]] = None,
    ):
        """Merge variables from included task files into the entry point"""
        if existing_options is None:
            existing_options = {}

        included_files = analysis.get("file_includes_map", {}).get(
            entry_point_name, set()
        )
        file_variables = analysis.get("file_variables", {})

        for included_file in included_files:
            if included_file in file_variables:
                file_vars = file_variables[included_file]
                for var_name in file_vars:
                    if var_name not in entry_point.options:
                        existing_opt = existing_options.get(var_name, {})
                        existing_desc = existing_opt.get("description")
                        existing_version = existing_opt.get("version_added")
                        is_existing = existing_opt.get("_existing", False)

                        if existing_desc:
                            description = existing_desc
                            self.log_trace(f"Using existing description for {var_name}")
                        else:
                            description = f"Variable used in included task file: {included_file}.yml"

                        version_added = None
                        if existing_version:
                            version_added = existing_version
                            self.log_trace(
                                f"Using existing version_added for {var_name}: {version_added}"
                            )
                        elif is_existing:
                            self.log_trace(
                                f"Variable {var_name} existed in argument specs - not adding version_added"
                            )
                        else:
                            version_added = analysis["version"]
                            self.log_trace(
                                f"Adding version_added for new task variable {var_name}: {version_added}"
                            )

                        has_default = var_name in analysis.get(
                            "defaults", {}
                        ) or var_name in analysis.get("vars", {})

                        arg_spec = ArgumentSpec(
                            name=var_name,
                            type="str",
                            description=description,
                            version_added=version_added,
                            required=not has_default,
                        )
                        entry_point.options[var_name] = arg_spec
                        req_status = "required" if not has_default else "optional"
                        self.log_debug(
                            f"Added {req_status} variable from {included_file}.yml: {var_name}"
                        )

        def collect_recursive_variables(file_name: str, visited: set):
            if file_name in visited:
                return
            visited.add(file_name)

            if file_name in file_variables:
                file_vars = file_variables[file_name]
                for var_name in file_vars:
                    if var_name not in entry_point.options:
                        existing_opt = existing_options.get(var_name, {})
                        existing_desc = existing_opt.get("description")
                        existing_version = existing_opt.get("version_added")
                        is_existing = existing_opt.get("_existing", False)

                        if existing_desc:
                            description = existing_desc
                            self.log_trace(f"Using existing description for {var_name}")
                        else:
                            description = (
                                f"Variable used in included task file: {file_name}.yml"
                            )

                        version_added = None
                        if existing_version:
                            version_added = existing_version
                            self.log_trace(
                                f"Using existing version_added for {var_name}: {version_added}"
                            )
                        elif is_existing:
                            self.log_trace(
                                f"Variable {var_name} existed in argument specs - not adding version_added"
                            )
                        else:
                            version_added = analysis["version"]
                            self.log_trace(
                                f"Adding version_added for new task variable {var_name}: {version_added}"
                            )

                        has_default = var_name in analysis.get(
                            "defaults", {}
                        ) or var_name in analysis.get("vars", {})

                        arg_spec = ArgumentSpec(
                            name=var_name,
                            type="str",
                            description=description,
                            version_added=version_added,
                            required=not has_default,
                        )
                        entry_point.options[var_name] = arg_spec
                        req_status = "required" if not has_default else "optional"
                        self.log_debug(
                            f"Added {req_status} variable from {file_name}.yml (recursive): {var_name}"
                        )

            sub_includes = analysis.get("file_includes_map", {}).get(file_name, set())
            for sub_included in sub_includes:
                collect_recursive_variables(sub_included, visited)

        visited_files = set()
        for included_file in included_files:
            collect_recursive_variables(included_file, visited_files)

    def _add_entry_point_variables(
        self,
        entry_point: EntryPointSpec,
        entry_point_name: str,
        analysis: Dict[str, Any],
        existing_options: Dict[str, Dict[str, Any]] = None,
    ):
        """Add variables found directly in the entry point file itself"""
        if existing_options is None:
            existing_options = {}

        file_variables = analysis.get("file_variables", {})
        entry_point_vars = file_variables.get(entry_point_name, set())

        self.log_debug(
            f"Adding variables from entry point file '{entry_point_name}': {sorted(entry_point_vars) if entry_point_vars else 'none'}"
        )

        for var_name in entry_point_vars:
            if var_name not in entry_point.options:
                existing_opt = existing_options.get(var_name, {})
                existing_desc = existing_opt.get("description")
                existing_version = existing_opt.get("version_added")
                is_existing = existing_opt.get("_existing", False)

                if existing_desc:
                    description = existing_desc
                    self.log_trace(f"Using existing description for {var_name}")
                else:
                    description = f"Variable used in {entry_point_name} entry point"

                version_added = None
                if existing_version:
                    version_added = existing_version
                    self.log_trace(
                        f"Using existing version_added for {var_name}: {version_added}"
                    )
                elif is_existing:
                    self.log_trace(
                        f"Variable {var_name} existed in argument specs - not adding version_added"
                    )
                else:
                    version_added = analysis["version"]
                    self.log_trace(
                        f"Adding version_added for new entry point variable {var_name}: {version_added}"
                    )

                has_default = var_name in analysis.get(
                    "defaults", {}
                ) or var_name in analysis.get("vars", {})

                arg_spec = ArgumentSpec(
                    name=var_name,
                    type="str",
                    description=description,
                    version_added=version_added,
                    required=not has_default,
                )
                entry_point.options[var_name] = arg_spec
                req_status = "required" if not has_default else "optional"
                self.log_debug(
                    f"Added {req_status} variable from entry point {entry_point_name}: {var_name}"
                )

    def _create_entry_point_spec(
        self,
        entry_point_name: str,
        role_name: str,
        analysis: Dict[str, Any],
        existing_specs: Dict[str, Any] = None,
    ) -> EntryPointSpec:
        """Create an entry point specification from analysis data, preserving existing descriptions"""
        if existing_specs is None:
            existing_specs = {}

        self.log_debug(f"Creating specs for entry point: {entry_point_name}")

        if "description" in existing_specs:
            description = existing_specs["description"]
            self.log_trace(f"Using existing description for entry point")
        elif analysis.get("meta_description"):
            description = analysis["meta_description"]
            self.log_trace(f"Using description from meta/main.yml")
        else:
            description_lines = [
                f"Automatically generated argument specification for the {role_name} role.",
                f"Entry point: {entry_point_name}",
            ]

            included_files = analysis.get("file_includes_map", {}).get(
                entry_point_name, set()
            )
            if included_files:
                description_lines.append(
                    f"Includes task files: {', '.join(sorted(included_files))}"
                )

            description = description_lines

        if "short_description" in existing_specs:
            short_description = existing_specs["short_description"]
            self.log_trace(f"Using existing short_description for entry point")
        elif analysis.get("meta_short_description"):
            short_description = analysis["meta_short_description"]
            self.log_trace(f"Using short_description from meta/main.yml")
        else:
            short_description = f"Auto-generated specs for {role_name} role - {entry_point_name} entry point"

        if "author" in existing_specs:
            author = existing_specs["author"]
            self.log_trace(f"Using existing author for entry point")
        else:
            author = analysis.get("authors", [])
            if author:
                self.log_trace(
                    f"Using author(s) from meta/main.yml: {', '.join(author)}"
                )

        entry_point = EntryPointSpec(
            name=entry_point_name,
            short_description=short_description,
            description=description,
            author=author,
        )

        existing_options = existing_specs.get("options", {})
        if existing_options:
            self.log_trace(
                f"Existing options for entry point: {list(existing_options.keys())}"
            )

        for var_name, var_value in analysis["defaults"].items():
            existing_opt = existing_options.get(var_name, {})
            existing_desc = existing_opt.get("description")
            existing_version = existing_opt.get("version_added")
            is_existing = existing_opt.get("_existing", False)

            self.log_trace(
                f"Processing default variable '{var_name}': existing={is_existing}, has_existing_version={bool(existing_version)}"
            )

            arg_spec = self._infer_argument_spec(
                var_name,
                var_value,
                existing_desc,
                existing_version,
                is_existing,
                analysis["version"],
            )
            entry_point.options[var_name] = arg_spec

        for var_name, var_value in analysis["vars"].items():
            if var_name not in entry_point.options:
                existing_opt = existing_options.get(var_name, {})
                existing_desc = existing_opt.get("description")
                existing_version = existing_opt.get("version_added")
                is_existing = existing_opt.get("_existing", False)
                arg_spec = self._infer_argument_spec(
                    var_name,
                    var_value,
                    existing_desc,
                    existing_version,
                    is_existing,
                    analysis["version"],
                )
                if not existing_desc:
                    arg_spec.description = f"{arg_spec.description} (defined in vars)"
                entry_point.options[var_name] = arg_spec

        self._add_entry_point_variables(
            entry_point, entry_point_name, analysis, existing_options
        )

        self._merge_included_variables(
            entry_point, entry_point_name, analysis, existing_options
        )

        return entry_point

    def process_single_role(self, role_path: str, role_name: str = None):
        """Process a single role to generate argument specs"""
        role_dir = Path(role_path)
        if role_name is None:
            role_name = role_dir.name

        if not self.current_role:
            self.current_role = role_name

        self.log_verbose("Analyzing role structure...")
        self.variable_context.clear()

        analysis = self.analyze_role_structure(role_path)

        existing_specs = self.load_existing_specs(role_path)
        if existing_specs:
            self.log_verbose(
                f"Loaded existing specs for entry points: {list(existing_specs.keys())}"
            )
        else:
            self.log_verbose("No existing argument specs found")

        self.entry_points.clear()

        for entry_point_name in analysis["entry_points"]:
            existing_entry_specs = existing_specs.get(entry_point_name, {})
            if existing_entry_specs:
                existing_options_count = len(existing_entry_specs.get("options", {}))
                self.log_debug(
                    f"Entry point '{entry_point_name}' has {existing_options_count} existing options"
                )
            else:
                self.log_debug(
                    f"Entry point '{entry_point_name}' has no existing specs"
                )

            entry_point = self._create_entry_point_spec(
                entry_point_name, role_name, analysis, existing_entry_specs
            )
            self.add_entry_point(entry_point)
            self.stats["entry_points_created"] += 1

        self.log_verbose(
            f"Generated specs for {len(analysis['entry_points'])} entry point(s)"
        )
        self.log_verbose(f"Found {len(analysis['defaults'])} default variables")

        total_vars = 0
        new_vars = 0
        existing_vars = 0

        for entry_point_name in analysis["entry_points"]:
            if entry_point_name in self.entry_points:
                entry_point = self.entry_points[entry_point_name]
                for var_name, arg_spec in entry_point.options.items():
                    total_vars += 1
                    if arg_spec.version_added:
                        if arg_spec.version_added == analysis["version"]:
                            new_vars += 1
                        else:
                            existing_vars += 1
                    else:
                        existing_vars += 1

        self.stats["total_variables"] += total_vars
        self.stats["new_variables"] += new_vars
        self.stats["existing_variables"] += existing_vars

        if total_vars > 0:
            self.log_verbose(
                f"Version tracking: {new_vars} new variables, {existing_vars} existing variables"
            )

        if self.collection_mode:
            self.save_role_specs(role_path, role_name)

    def load_existing_specs(self, role_path: str) -> Dict[str, Dict[str, Any]]:
        """Load existing argument specs to preserve manual descriptions"""
        specs_file = Path(role_path) / "meta" / "argument_specs.yml"
        existing_specs = {}

        if not specs_file.exists():
            return existing_specs

        try:
            with open(specs_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return existing_specs

                specs_data = yaml.safe_load(content)
                if (
                    not isinstance(specs_data, dict)
                    or "argument_specs" not in specs_data
                ):
                    return existing_specs

                for entry_name, entry_data in specs_data["argument_specs"].items():
                    if not isinstance(entry_data, dict):
                        continue

                    entry_specs = {}

                    if "description" in entry_data:
                        entry_specs["description"] = entry_data["description"]
                    if "short_description" in entry_data:
                        entry_specs["short_description"] = entry_data[
                            "short_description"
                        ]
                    if "author" in entry_data:
                        entry_specs["author"] = entry_data["author"]

                    if "options" in entry_data and isinstance(
                        entry_data["options"], dict
                    ):
                        entry_specs["options"] = {}
                        for opt_name, opt_data in entry_data["options"].items():
                            opt_spec = {"_existing": True}

                            if isinstance(opt_data, dict):
                                if "description" in opt_data:
                                    opt_spec["description"] = opt_data["description"]
                                if "version_added" in opt_data:
                                    opt_spec["version_added"] = opt_data[
                                        "version_added"
                                    ]
                            else:
                                self.log_debug(
                                    f"Warning: Variable '{opt_name}' in existing specs is not properly structured"
                                )

                            entry_specs["options"][opt_name] = opt_spec

                    existing_specs[entry_name] = entry_specs

                self.log_debug(
                    f"Loaded existing specs with {len(existing_specs)} entry point(s)"
                )
                for ep_name, ep_data in existing_specs.items():
                    options_count = len(ep_data.get("options", {}))
                    self.log_trace(
                        f"Entry point '{ep_name}': {options_count} existing options"
                    )

        except yaml.YAMLError as e:
            self.log_verbose(
                f"Warning: Could not parse existing specs file {specs_file}: {e}"
            )
        except Exception as e:
            self.log_verbose(
                f"Warning: Could not load existing specs file {specs_file}: {e}"
            )

        return existing_specs

    # ---------------------------------------------------------------- interactive mode

    def interactive_mode(self):
        """Interactive mode to create argument specs"""
        print("=== Ansible Argument Specs Generator ===")
        print("Interactive mode - Press Ctrl+C to exit\n")

        try:
            entry_name = input("Entry point name (default: main): ").strip() or "main"
            short_desc = input("Short description: ").strip()

            print("\nLong description (press Enter on empty line to finish):")
            description = []
            while True:
                line = input()
                if not line:
                    break
                description.append(line)

            print("\nAuthor(s) (press Enter on empty line to finish):")
            authors = []
            while True:
                line = input().strip()
                if not line:
                    break
                authors.append(line)

            entry_point = EntryPointSpec(
                name=entry_name,
                short_description=short_desc,
                description=description,
                author=authors,
            )

            print(f"\n=== Adding arguments for '{entry_name}' entry point ===")
            while True:
                print("\nAdd new argument? (y/n): ", end="")
                if input().lower() != "y":
                    break

                arg_spec = self._get_argument_interactive()
                if arg_spec:
                    entry_point.options[arg_spec.name] = arg_spec

            self._get_conditionals_interactive(entry_point)

            self.add_entry_point(entry_point)

        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)

    def _get_argument_interactive(self) -> Optional[ArgumentSpec]:
        """Get argument specification interactively"""
        try:
            name = input("Argument name: ").strip()
            if not name:
                return None

            print(f"Available types: {', '.join([t.value for t in ArgumentType])}")
            arg_type = input("Type (default: str): ").strip() or "str"

            description = input("Description: ").strip()

            required = input("Required? (y/n, default: n): ").lower().startswith("y")

            default_val = input("Default value (press Enter for none): ").strip()
            if default_val:
                if arg_type == "bool":
                    default_val = default_val.lower() in ["true", "yes", "1", "on"]
                elif arg_type == "int":
                    default_val = int(default_val)
                elif arg_type == "float":
                    default_val = float(default_val)
                elif arg_type in ["list", "dict"]:
                    try:
                        default_val = json.loads(default_val)
                    except json.JSONDecodeError:
                        print("Warning: Could not parse as JSON, using as string")
            else:
                default_val = None

            choices = None
            if input("Has choices? (y/n): ").lower().startswith("y"):
                choices_str = input("Choices (comma-separated): ")
                choices = [c.strip() for c in choices_str.split(",") if c.strip()]

            elements = None
            if arg_type in ["list", "dict"]:
                elements = (
                    input(f"Element type for {arg_type} (default: str): ").strip()
                    or "str"
                )

            version_added = None
            version_input = input("Version added (press Enter for none): ").strip()
            if version_input:
                version_added = version_input

            return ArgumentSpec(
                name=name,
                type=arg_type,
                required=required,
                default=default_val,
                choices=choices,
                description=description,
                elements=elements,
                version_added=version_added,
            )

        except (ValueError, KeyboardInterrupt) as e:
            print(f"Error: {e}")
            return None

    def _get_conditionals_interactive(self, entry_point: EntryPointSpec):
        """Get conditional requirements interactively"""
        print("\n=== Conditional Requirements ===")

        if input("Add required_if conditions? (y/n): ").lower().startswith("y"):
            entry_point.required_if = []
            while True:
                condition = input("Condition (param,value,required_params): ").strip()
                if not condition:
                    break
                try:
                    parts = [p.strip() for p in condition.split(",")]
                    if len(parts) >= 3:
                        param = parts[0]
                        value = parts[1]
                        required = parts[2:]
                        entry_point.required_if.append([param, value, required])
                except Exception as e:
                    print(f"Error parsing condition: {e}")

        if input("Add required_one_of groups? (y/n): ").lower().startswith("y"):
            entry_point.required_one_of = []
            while True:
                group = input("Group (comma-separated params): ").strip()
                if not group:
                    break
                params = [p.strip() for p in group.split(",")]
                entry_point.required_one_of.append(params)

        if input("Add mutually_exclusive groups? (y/n): ").lower().startswith("y"):
            entry_point.mutually_exclusive = []
            while True:
                group = input("Group (comma-separated params): ").strip()
                if not group:
                    break
                params = [p.strip() for p in group.split(",")]
                entry_point.mutually_exclusive.append(params)

        if input("Add required_together groups? (y/n): ").lower().startswith("y"):
            entry_point.required_together = []
            while True:
                group = input("Group (comma-separated params): ").strip()
                if not group:
                    break
                params = [p.strip() for p in group.split(",")]
                entry_point.required_together.append(params)

    # --------------------------------------------------------- from file loaders

    def from_defaults_file(self, defaults_file: str, entry_name: str = "main"):
        """Generate specs from a defaults/main.yml file"""
        if not os.path.exists(defaults_file):
            raise ConfigError(f"Defaults file not found: {defaults_file}")

        with open(defaults_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                self.log_verbose(f"Warning: Defaults file is empty: {defaults_file}")
                defaults = {}
            else:
                defaults = yaml.safe_load(content)
                if not isinstance(defaults, dict):
                    self.log_verbose(
                        f"Warning: Defaults file does not contain a dictionary: {defaults_file}"
                    )
                    defaults = {}

        entry_point = EntryPointSpec(
            name=entry_name,
            short_description=f"Auto-generated from {defaults_file}",
        )

        for var_name, var_value in defaults.items():
            arg_spec = self._infer_argument_spec(
                var_name, var_value, None, None, False, "1.0.0"
            )
            entry_point.options[var_name] = arg_spec

        self.add_entry_point(entry_point)
        self.log_info(
            f"Generated specs for {len(entry_point.options)} variables from {defaults_file}",
            role_prefix=False,
        )

    def from_config_file(self, config_file: str):  # noqa: C901
        """Generate specs from a configuration file (JSON or YAML)"""
        if not os.path.exists(config_file):
            raise ConfigError(f"Config file not found: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                raise ConfigError(f"Config file is empty: {config_file}")

            if config_file.endswith(".json"):
                config = json.loads(content)
            else:
                config = yaml.safe_load(content)

        if not isinstance(config, dict):
            raise ConfigError(f"Config file must contain a dictionary: {config_file}")

        if "entry_points" not in config:
            raise ConfigError(
                f"Config file must contain 'entry_points' section: {config_file}"
            )

        for entry_name, entry_config in config.get("entry_points", {}).items():
            if not isinstance(entry_config, dict):
                self.log_verbose(
                    f"Warning: Skipping invalid entry point '{entry_name}' - must be a dictionary"
                )
                continue

            entry_point = EntryPointSpec(
                name=entry_name,
                short_description=entry_config.get("short_description", ""),
                description=entry_config.get("description", []),
                author=entry_config.get("author", []),
            )

            for arg_name, arg_config in entry_config.get("arguments", {}).items():
                if not isinstance(arg_config, dict):
                    self.log_verbose(
                        f"Warning: Skipping invalid argument '{arg_name}' - must be a dictionary"
                    )
                    continue

                arg_spec = ArgumentSpec(
                    name=arg_name,
                    type=arg_config.get("type", "str"),
                    required=arg_config.get("required", False),
                    default=arg_config.get("default"),
                    choices=arg_config.get("choices"),
                    description=arg_config.get("description"),
                    elements=arg_config.get("elements"),
                    version_added=arg_config.get("version_added"),
                )
                entry_point.options[arg_name] = arg_spec

            entry_point.required_if = entry_config.get("required_if", [])
            entry_point.required_one_of = entry_config.get("required_one_of", [])
            entry_point.mutually_exclusive = entry_config.get("mutually_exclusive", [])
            entry_point.required_together = entry_config.get("required_together", [])

            self.add_entry_point(entry_point)

        self.log_info(
            f"Generated specs from config file: {config_file}", role_prefix=False
        )

    # --------------------------------------------------------------- validation

    def validate_specs(self) -> bool:
        """Validate the generated argument specs"""
        valid = True

        for entry_name, entry_point in self.entry_points.items():
            self.log_info(f"Validating entry point: {entry_name}")

            if not entry_point.short_description:
                self.log_verbose(f"No short_description for {entry_name}")

            for arg_name, arg_spec in entry_point.options.items():
                if arg_spec.type not in [t.value for t in ArgumentType]:
                    self.log_error(
                        f"Invalid type '{arg_spec.type}' for argument '{arg_name}'"
                    )
                    valid = False

                if arg_spec.type in ["list", "dict"] and not arg_spec.elements:
                    self.log_verbose(
                        f"No elements type specified for {arg_spec.type} argument '{arg_name}'"
                    )

            all_args = set(entry_point.options.keys())

            for condition_type, conditions in [
                ("required_if", entry_point.required_if or []),
                ("required_one_of", entry_point.required_one_of or []),
                ("mutually_exclusive", entry_point.mutually_exclusive or []),
                ("required_together", entry_point.required_together or []),
            ]:
                for condition in conditions:
                    if condition_type == "required_if":
                        if len(condition) >= 3:
                            param = condition[0]
                            required_params = (
                                condition[2]
                                if isinstance(condition[2], list)
                                else [condition[2]]
                            )

                            if param not in all_args:
                                self.log_error(
                                    f"{condition_type} references unknown argument '{param}'"
                                )
                                valid = False

                            for req_param in required_params:
                                if req_param not in all_args:
                                    self.log_error(
                                        f"{condition_type} references unknown argument '{req_param}'"
                                    )
                                    valid = False
                    else:
                        for param in condition:
                            if param not in all_args:
                                self.log_error(
                                    f"{condition_type} references unknown argument '{param}'"
                                )
                                valid = False

        return valid
