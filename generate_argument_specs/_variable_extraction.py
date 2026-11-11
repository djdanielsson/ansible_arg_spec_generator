"""
Mixin class for extracting variables from Ansible task and template files.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from ._constants import _BUILTIN_EXACT, _BUILTIN_PREFIXES, _NON_VARIABLES
from ._task_analysis import TaskAnalyzer, include_target, walk_tasks


class VariableExtractionMixin:
    """Methods for extracting and analysing variables in task files."""

    def extract_variables_from_task_file(self, task_file_path: Path) -> Set[str]:
        """Extract external names, respecting task-local and loop bindings."""
        return TaskAnalyzer(self).analyze_file(Path(task_file_path)).names

    def _analyze_variable_usage_context(self, content: str, task_file_path: Path):
        """Analyze how variables are used in task files to generate better descriptions"""
        try:
            tasks = yaml.safe_load(content)
            if not isinstance(tasks, list):
                return

            for task in walk_tasks(tasks):
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

        task = {
            key.rsplit(".", 1)[-1]: value
            for key, value in task.items()
            if isinstance(key, str)
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

        return sorted(
            TaskAnalyzer(self)
            .value_usage(value)
            .filtered(self._is_valid_role_variable)
            .names
        )

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

        lowered = var_name.lower()
        if (
            any(var_name.startswith(prefix) for prefix in _BUILTIN_PREFIXES)
            or lowered in _BUILTIN_EXACT
            or lowered in _NON_VARIABLES
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
        """Return static include paths, retaining directories and walking blocks."""
        _, tasks = TaskAnalyzer(self).load(Path(task_file_path))
        includes = set()
        for task in walk_tasks(tasks):
            target = include_target(task)
            if target:
                path = Path(target)
                if path.suffix in {".yml", ".yaml"}:
                    path = path.with_suffix("")
                includes.add(path.as_posix())
        return includes
