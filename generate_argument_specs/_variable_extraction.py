"""
Mixin class for extracting variables from Ansible task and template files.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from ._constants import _BUILTIN_PREFIXES, _NON_VARIABLES


class VariableExtractionMixin:
    """Methods for extracting and analysing variables in task files."""

    def extract_variables_from_task_file(self, task_file_path: Path) -> Set[str]:
        """Extract variables used in a task file"""
        variables = set()

        try:
            with open(task_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                return variables

            self._analyze_variable_usage_context(content, task_file_path)

            # Find all registered variables to exclude them
            registered_vars = set()
            register_patterns = [
                r"register:\s*([a-zA-Z_][a-zA-Z0-9_]*)",
                r"set_fact:\s*\n\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:",
            ]

            for pattern in register_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    var_name = match.strip()
                    if var_name:
                        registered_vars.add(var_name)

            # Also find properties/attributes of registered variables to exclude them
            registered_properties = set()
            if registered_vars:
                property_patterns = [
                    r"when:\s*([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)",
                    r"changed_when:\s*([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)",
                    r"failed_when:\s*([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)",
                    r"until:\s*([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)",
                    r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)",
                ]

                for pattern in property_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    for var_name, property_name in matches:
                        if var_name in registered_vars:
                            registered_properties.add(property_name)

            excluded_vars = registered_vars | registered_properties
            if excluded_vars:
                self.log_trace(
                    f"Excluding registered variables and their properties in {task_file_path.name}: {', '.join(sorted(excluded_vars))}"
                )

            patterns = [
                r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}",
                r"when:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not)",
                r"([a-zA-Z_][a-zA-Z0-9_]*)\s+is\s+(?:defined|not defined)",
                r"assert:\s*\n\s*that:\s*\n(?:\s*-\s*)+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not|in)",
                r"-\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+is\s+(?:defined|not defined)",
                r"-\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|>|<|>=|<=)",
                r"-\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+(?:in|not in)",
                r'-\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not|in|>|<|>=|<=)',
                r"failed_when:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not)",
                r"changed_when:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not)",
                r"that:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not|in)",
                r"that:\s*[|>]\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:==|!=|is|not)",
                r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*default",
                r'with_items:\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}["\']?',
                r'loop:\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}["\']?',
                r"when:\s*[a-zA-Z_][a-zA-Z0-9_]*\.([a-zA-Z_][a-zA-Z0-9_]*)",
                r':\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}["\']?',
                r'environment:\s*\n(?:\s*[A-Z_]+:\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}["\']?\s*\n?)+',
                r'"[^"]*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}[^"]*"',
                r"'[^']*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}[^']*'",
                r'tags:\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}["\']?',
                r"vars:\s*\n\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
                for match in matches:
                    if isinstance(match, tuple):
                        for var_name in match:
                            if var_name and var_name.strip():
                                var_name = var_name.strip()
                                if (
                                    self._is_valid_role_variable(var_name)
                                    and var_name not in excluded_vars
                                ):
                                    variables.add(var_name)
                    else:
                        var_name = match.strip()
                        if (
                            self._is_valid_role_variable(var_name)
                            and var_name not in excluded_vars
                        ):
                            variables.add(var_name)

            task_name_pattern = r'name:\s*["\']?[^"\'\n]*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}'
            task_name_matches = re.findall(
                task_name_pattern, content, re.MULTILINE | re.DOTALL
            )
            for match in task_name_matches:
                var_name = match.strip()
                if (
                    self._is_valid_role_variable(var_name)
                    and var_name not in excluded_vars
                ):
                    variables.add(var_name)

            if variables:
                self.log_trace(
                    f"Variables found in {task_file_path.name}: {', '.join(sorted(variables))}"
                )

        except UnicodeDecodeError as e:
            self.log_verbose(f"Warning: Could not decode file {task_file_path}: {e}")
        except (OSError, IOError) as e:
            self.log_verbose(f"Warning: Could not read file {task_file_path}: {e}")
        except re.error as e:
            self.log_verbose(f"Warning: Regex pattern error in {task_file_path}: {e}")
        except Exception as e:
            self.log_verbose(
                f"Warning: Could not extract variables from {task_file_path}: {e}"
            )

        return variables

    def _analyze_variable_usage_context(self, content: str, task_file_path: Path):
        """Analyze how variables are used in task files to generate better descriptions"""
        try:
            tasks = yaml.safe_load(content)
            if not isinstance(tasks, list):
                return

            for task in tasks:
                if not isinstance(task, dict):
                    continue

                self._analyze_task_modules(task, task_file_path)

        except yaml.YAMLError:
            self._analyze_content_patterns(content, task_file_path)
        except Exception as e:
            self.log_debug(
                f"Could not analyze variable context in {task_file_path}: {e}"
            )

    def _analyze_task_modules(self, task: dict, task_file_path: Path):
        """Analyze specific Ansible modules and their variable usage"""
        module_contexts = {
            "copy": {
                "src": "source file path",
                "dest": "destination file path",
                "content": "file content",
            },
            "template": {"src": "template file path", "dest": "destination file path"},
            "file": {
                "path": "file or directory path",
                "state": "file state",
                "mode": "file permissions",
            },
            "lineinfile": {
                "path": "target file path",
                "line": "line content",
                "regexp": "search pattern",
            },
            "package": {"name": "package name", "state": "package state"},
            "yum": {"name": "package name", "state": "package state"},
            "apt": {"name": "package name", "state": "package state"},
            "pip": {"name": "Python package name", "state": "package state"},
            "service": {
                "name": "service name",
                "state": "service state",
                "enabled": "service startup",
            },
            "systemd": {
                "name": "systemd service name",
                "state": "service state",
                "enabled": "service startup",
            },
            "user": {
                "name": "username",
                "state": "user account state",
                "home": "home directory",
            },
            "group": {"name": "group name", "state": "group state"},
            "command": {"cmd": "command to execute", "chdir": "working directory"},
            "shell": {"cmd": "shell command", "chdir": "working directory"},
            "script": {"cmd": "script path", "chdir": "working directory"},
            "uri": {
                "url": "target URL",
                "method": "HTTP method",
                "headers": "HTTP headers",
            },
            "get_url": {"url": "source URL", "dest": "destination path"},
            "unarchive": {"src": "archive file path", "dest": "extraction path"},
            "archive": {"path": "source path", "dest": "archive destination"},
        }

        for module_name, param_contexts in module_contexts.items():
            if module_name in task:
                module_params = task[module_name]
                if isinstance(module_params, dict):
                    for param, context_desc in param_contexts.items():
                        if param in module_params:
                            param_value = module_params[param]
                            variables = self._extract_variables_from_value(param_value)
                            for var in variables:
                                self._store_variable_context(
                                    var,
                                    {
                                        "context": context_desc,
                                        "module": module_name,
                                        "parameter": param,
                                        "file": task_file_path.stem,
                                    },
                                )

    def _analyze_content_patterns(self, content: str, task_file_path: Path):
        """Analyze content patterns when YAML parsing fails"""
        context_patterns = {
            r'dest:\s*["\']?.*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}': "destination file path",
            r'src:\s*["\']?.*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}': "source file path",
            r'name:\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}': "resource name",
            r'state:\s*["\']?\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}': "resource state",
            r"enabled:\s*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}": "enable/disable setting",
            r"port:\s*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}": "port number",
            r'url:\s*["\']?.*\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}': "URL address",
        }

        for pattern, context_desc in context_patterns.items():
            matches = re.findall(pattern, content, re.MULTILINE)
            for var in matches:
                self._store_variable_context(
                    var, {"context": context_desc, "file": task_file_path.stem}
                )

    def _extract_variables_from_value(self, value) -> List[str]:
        """Extract variable names from parameter values"""
        if not isinstance(value, str):
            return []

        var_pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}"
        return re.findall(var_pattern, value)

    def _store_variable_context(self, var_name: str, context: Dict[str, Any]):
        """Store context information for a variable"""
        if var_name not in self.variable_context:
            self.variable_context[var_name] = {}

        context_key = (
            f"{context.get('module', 'unknown')}_{context.get('parameter', 'param')}"
        )
        self.variable_context[var_name][context_key] = context

    def _is_valid_role_variable(self, var_name: str) -> bool:
        """Check if a variable name is a valid role variable (not built-in)"""
        if not var_name or not isinstance(var_name, str):
            return False

        if (
            any(var_name.startswith(prefix) for prefix in _BUILTIN_PREFIXES)
            or var_name.lower() in _NON_VARIABLES
            or "(" in var_name
            or "[" in var_name
            or "." in var_name
            or " " in var_name
            or var_name.isdigit()
            or len(var_name) < 2
            or var_name.startswith("_")
        ):
            return False

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var_name):
            return False

        return True

    def parse_task_file_includes(self, task_file_path: Path) -> Set[str]:
        """Parse a task file to find included/imported files"""
        includes = set()

        try:
            with open(task_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                return includes

            self.log_trace(f"Parsing {task_file_path.name} for includes...")

            yaml_success = False
            try:
                tasks = yaml.safe_load(content)
                if isinstance(tasks, list):
                    for task in tasks:
                        if isinstance(task, dict):
                            for include_type in [
                                "include_tasks",
                                "import_tasks",
                                "include",
                                "import_playbook",
                            ]:
                                if include_type in task:
                                    include_value = task[include_type]
                                    if isinstance(include_value, str):
                                        include_file = Path(include_value).stem
                                        includes.add(include_file)
                                        self.log_trace(
                                            f"Found include via YAML: {include_file}"
                                        )
                                    elif (
                                        isinstance(include_value, dict)
                                        and "file" in include_value
                                    ):
                                        include_file = Path(include_value["file"]).stem
                                        includes.add(include_file)
                                        self.log_trace(
                                            f"Found include via YAML (dict): {include_file}"
                                        )
                    yaml_success = True
            except yaml.YAMLError as e:
                self.log_debug(f"YAML parsing failed for {task_file_path.name}: {e}")

            if not yaml_success or not includes:
                self.log_trace(f"Falling back to regex parsing...")
                include_patterns = [
                    r"(?:include_tasks|import_tasks|include|import_playbook):\s*([^\s\n\#]+)",
                    r"(?:include_tasks|import_tasks|include|import_playbook):\s*\n\s*file:\s*([^\s\n\#]+)",
                    r"block:\s*\n.*?include_tasks:\s*([^\s\n\#]+)",
                ]

                for pattern in include_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
                    for match in matches:
                        clean_match = match.strip("'\"").strip()
                        if clean_match and not clean_match.startswith("#"):
                            include_file = Path(clean_match).stem
                            if include_file and include_file != task_file_path.stem:
                                includes.add(include_file)
                                self.log_trace(
                                    f"Found include via regex: {include_file}"
                                )

            if not includes:
                self.log_trace(f"No includes found in {task_file_path.name}")

        except UnicodeDecodeError as e:
            self.log_error(f"Could not decode task file {task_file_path}: {e}")
        except (OSError, IOError) as e:
            self.log_error(f"Could not read task file {task_file_path}: {e}")
        except yaml.YAMLError as e:
            self.log_verbose(f"YAML parsing error in {task_file_path}: {e}")
        except re.error as e:
            self.log_error(f"Regex pattern error in {task_file_path}: {e}")
        except Exception as e:
            self.log_verbose(f"Could not parse task file {task_file_path}: {e}")

        return includes
