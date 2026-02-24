"""
Mixin class for type inference and smart description generation.
"""

from typing import Any

from ._models import ArgumentSpec


class TypeInferenceMixin:
    """Methods for inferring argument types and generating descriptions."""

    def _infer_argument_spec(
        self,
        name: str,
        value: Any,
        existing_description: str = None,
        existing_version_added: str = None,
        is_existing: bool = False,
        current_version: str = "1.0.0",
    ) -> ArgumentSpec:
        """Infer argument specification from a default value, preserving existing description and version info"""
        elements = None
        choices = None

        if isinstance(value, bool):
            arg_type = "bool"
        elif isinstance(value, int):
            arg_type = "int"
        elif isinstance(value, float):
            arg_type = "float"
        elif isinstance(value, list):
            arg_type = "list"
            elements = self._infer_list_element_type(value)
        elif isinstance(value, dict):
            arg_type = "dict"
        elif isinstance(value, str):
            arg_type = self._infer_string_type(name, value)
        else:
            arg_type = "str"

        if existing_description:
            description = existing_description
            self.log_trace(f"Using existing description for {name}")
        else:
            description = self._generate_smart_description(name, value, arg_type)

        version_added = None
        if existing_version_added:
            version_added = existing_version_added
            self.log_trace(f"Using existing version_added for {name}: {version_added}")
        elif is_existing:
            self.log_trace(
                f"Variable {name} existed in argument specs - not adding version_added"
            )
        else:
            version_added = current_version
            self.log_trace(
                f"Adding version_added for new variable {name}: {version_added}"
            )

        return ArgumentSpec(
            name=name,
            type=arg_type,
            default=value,
            description=description,
            elements=elements,
            choices=choices,
            version_added=version_added,
        )

    def _infer_list_element_type(self, value: list) -> str:
        """Infer the element type for a list"""
        if not value:
            return "str"

        type_counts = {}
        for elem in value:
            if isinstance(elem, dict):
                elem_type = "dict"
            elif isinstance(elem, int):
                elem_type = "int"
            elif isinstance(elem, bool):
                elem_type = "bool"
            elif isinstance(elem, float):
                elem_type = "float"
            else:
                elem_type = "str"

            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

        return max(type_counts.items(), key=lambda x: x[1])[0]

    def _infer_string_type(self, name: str, value: str) -> str:
        """Infer more specific types for string values based on name and content"""
        name_lower = name.lower()

        if any(
            keyword in name_lower
            for keyword in ["path", "dir", "directory", "file", "location"]
        ):
            if (
                value.startswith("/")
                or "\\" in value
                or any(
                    path_part in value
                    for path_part in ["home", "tmp", "var", "etc", "usr"]
                )
            ):
                return "path"

        if any(
            keyword in name_lower for keyword in ["url", "uri", "endpoint", "host"]
        ) or value.startswith(("http://", "https://", "ftp://")):
            return "str"

        if name_lower in ["state", "status", "mode", "action"] and value in [
            "present",
            "absent",
            "enabled",
            "disabled",
            "started",
            "stopped",
        ]:
            return "str"

        return "str"

    def _generate_smart_description(self, name: str, value: Any, arg_type: str) -> str:
        """Generate intelligent descriptions based on variable name, value, and usage context"""
        name_lower = name.lower()

        if name in self.variable_context:
            context_info = self.variable_context[name]
            best_context = None
            for context_key, context in context_info.items():
                if not best_context or "unknown" not in context_key:
                    best_context = context

            if best_context and "context" in best_context:
                context_desc = best_context["context"]
                module_info = f" (used in {best_context.get('module', 'task')})"
                base_desc = f"{context_desc}{module_info}"
                return self._format_description_by_type(base_desc, value, arg_type)

        description_patterns = {
            "enable": "Enable or disable functionality",
            "disable": "Disable functionality",
            "auth": "Authentication configuration",
            "token": "Authentication token",
            "key": "Authentication or encryption key",
            "secret": "Secret value for authentication",
            "cert": "SSL/TLS certificate",
            "ssl": "SSL/TLS configuration",
            "tls": "TLS configuration",
            "password": "Password for authentication",
            "user": "Username for authentication",
            "admin": "Administrator user or settings",
            "port": "Port number for network connection",
            "host": "Hostname or IP address",
            "address": "Network address",
            "url": "URL or web address",
            "endpoint": "API endpoint URL",
            "proxy": "Proxy server configuration",
            "dns": "DNS server or configuration",
            "interface": "Network interface",
            "bind": "Binding address or interface",
            "path": "File or directory path",
            "file": "File path",
            "dir": "Directory path",
            "directory": "Directory path",
            "folder": "Directory path",
            "location": "File or directory location",
            "home": "Home directory path",
            "root": "Root directory path",
            "base": "Base directory path",
            "log": "Log file path or configuration",
            "backup": "Backup file or directory path",
            "archive": "Archive file path",
            "temp": "Temporary directory path",
            "cache": "Cache directory path",
            "service": "Service name or configuration",
            "daemon": "Daemon process configuration",
            "process": "Process configuration",
            "pid": "Process ID or PID file path",
            "uid": "User ID",
            "gid": "Group ID",
            "owner": "File or resource owner",
            "group": "Group name or ID",
            "mode": "File permissions or operating mode",
            "permission": "Access permissions",
            "config": "Configuration settings",
            "setting": "Configuration setting",
            "option": "Configuration option",
            "param": "Parameter value",
            "variable": "Variable value",
            "value": "Configuration value",
            "default": "Default value",
            "override": "Override value",
            "state": "Desired state of the resource",
            "status": "Current status",
            "action": "Action to perform",
            "operation": "Operation to execute",
            "command": "Command to execute",
            "script": "Script path or content",
            "start": "Start the service or process",
            "stop": "Stop the service or process",
            "restart": "Restart the service or process",
            "reload": "Reload configuration",
            "timeout": "Timeout value in seconds",
            "retries": "Number of retry attempts",
            "delay": "Delay between operations in seconds",
            "interval": "Interval between operations",
            "frequency": "Frequency of execution",
            "schedule": "Schedule configuration",
            "cron": "Cron schedule expression",
            "debug": "Enable debug mode or output",
            "verbose": "Enable verbose output",
            "trace": "Enable trace logging",
            "force": "Force the operation even if it might cause issues",
            "check": "Perform check or validation",
            "validate": "Validate configuration or input",
            "test": "Test mode or configuration",
            "dry_run": "Perform dry run without making changes",
            "version": "Version specification",
            "package": "Package name or list",
            "repo": "Repository configuration",
            "repository": "Repository configuration",
            "branch": "Git branch name",
            "tag": "Version tag",
            "release": "Release version",
            "data": "Data content or configuration",
            "content": "File or resource content",
            "template": "Template file or content",
            "source": "Source file or URL",
            "destination": "Destination path",
            "target": "Target location or value",
            "output": "Output file or directory",
            "input": "Input file or data",
            "name": "Name identifier",
            "id": "Unique identifier",
            "uuid": "Unique identifier (UUID)",
            "label": "Label or tag",
            "description": "Description text",
        }

        if name_lower in description_patterns:
            base_desc = description_patterns[name_lower]
            return self._format_description_by_type(base_desc, value, arg_type)

        for pattern, desc in description_patterns.items():
            if pattern in name_lower:
                base_desc = desc
                return self._format_description_by_type(base_desc, value, arg_type)

        return self._generate_fallback_description(name, value, arg_type)

    def _format_description_by_type(
        self, base_desc: str, value: Any, arg_type: str
    ) -> str:
        """Format description based on value type and content"""
        if isinstance(value, bool):
            if value:
                return f"{base_desc} (enabled by default)"
            else:
                return f"{base_desc} (disabled by default)"
        elif isinstance(value, (int, float)):
            if arg_type in ["int", "float"]:
                return f"{base_desc} (default: {value})"
            else:
                return f"{base_desc}"
        elif isinstance(value, list):
            if len(value) == 0:
                return f"{base_desc} (list, empty by default)"
            elif len(value) == 1:
                return f"{base_desc} (list with default item)"
            else:
                return f"{base_desc} (list with {len(value)} default items)"
        elif isinstance(value, dict):
            if len(value) == 0:
                return f"{base_desc} (dictionary, empty by default)"
            else:
                return f"{base_desc} (dictionary with default configuration)"
        elif isinstance(value, str):
            if value == "":
                return f"{base_desc} (empty by default)"
            elif len(value) > 50:
                return f"{base_desc} (configured with default value)"
            else:
                return f"{base_desc} (default: '{value}')"
        else:
            return base_desc

    def _generate_fallback_description(
        self, name: str, value: Any, arg_type: str
    ) -> str:
        """Generate fallback descriptions with better context"""
        name_parts = name.lower().replace("-", "_").split("_")
        cleaned_name = name.replace("_", " ").replace("-", " ")

        if len(name_parts) > 1:
            if name_parts[-1] in ["list", "items", "array"]:
                return f"List of {' '.join(name_parts[:-1])}"
            elif name_parts[-1] in ["config", "conf", "cfg"]:
                return f"Configuration settings for {' '.join(name_parts[:-1])}"
            elif name_parts[-1] in ["enabled", "enable"]:
                return f"Enable {' '.join(name_parts[:-1])} functionality"
            elif name_parts[-1] in ["disabled", "disable"]:
                return f"Disable {' '.join(name_parts[:-1])} functionality"
            elif name_parts[0] in ["is", "has", "should", "can"]:
                return f"Whether to {' '.join(name_parts[1:])}"

        if arg_type == "bool":
            return f"Boolean flag to control {cleaned_name}"
        elif arg_type in ["int", "float"]:
            return f"Numeric value for {cleaned_name}"
        elif arg_type == "list":
            return f"List of {cleaned_name} items"
        elif arg_type == "dict":
            return f"Configuration dictionary for {cleaned_name}"
        elif arg_type == "path":
            return f"File system path for {cleaned_name}"
        else:
            return f"Configuration value for {cleaned_name}"
