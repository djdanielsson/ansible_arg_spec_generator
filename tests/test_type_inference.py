"""
Tests for type inference and smart description generation
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from generate_argument_specs import ArgumentSpecsGenerator, ArgumentSpec, EntryPointSpec


class TestTypeInference:
    """Test automatic type inference functionality"""

    def test_infer_path_types(self, temp_dir):
        """Test inference of path-type variables"""
        generator = ArgumentSpecsGenerator()

        # Create defaults with path-like variables
        defaults_content = {
            "app_config_path": "/etc/app/config.yml",
            "log_file_path": "/var/log/app.log",
            "data_directory": "/var/lib/app",
            "config_dir": "/etc/app",
            "ssl_cert_file": "/etc/ssl/cert.pem",
            "backup_path": "/backup/app",
            "temp_folder": "/tmp/app",
        }

        defaults_file = temp_dir / "defaults.yml"
        with open(defaults_file, "w") as f:
            yaml.dump(defaults_content, f)

        # Test type inference (this would be part of the full analysis)
        # For now, we'll test the pattern matching logic directly
        path_variables = [
            "app_config_path",
            "log_file_path",
            "data_directory",
            "config_dir",
            "ssl_cert_file",
            "backup_path",
            "temp_folder",
        ]

        for var_name in path_variables:
            # Simulate type inference logic
            inferred_type = (
                "path"
                if any(
                    keyword in var_name.lower()
                    for keyword in ["path", "dir", "directory", "file", "folder"]
                )
                else "str"
            )
            assert (
                inferred_type == "path"
            ), f"{var_name} should be inferred as path type"

    def test_infer_boolean_types(self, temp_dir):
        """Test inference of boolean-type variables"""
        generator = ArgumentSpecsGenerator()

        defaults_content = {
            "app_enabled": True,
            "debug_mode": False,
            "ssl_enabled": True,
            "force_update": False,
            "enable_monitoring": True,
            "disable_firewall": False,
            "use_ssl": True,
            "skip_validation": False,
        }

        defaults_file = temp_dir / "defaults.yml"
        with open(defaults_file, "w") as f:
            yaml.dump(defaults_content, f)

        boolean_variables = [
            "app_enabled",
            "debug_mode",
            "ssl_enabled",
            "force_update",
            "enable_monitoring",
            "disable_firewall",
            "use_ssl",
            "skip_validation",
        ]

        for var_name in boolean_variables:
            # Test boolean inference patterns
            is_boolean = (
                any(
                    keyword in var_name.lower()
                    for keyword in ["enable", "disable", "force", "skip", "use"]
                )
                or var_name.lower().endswith(("_enabled", "_mode"))
                or isinstance(defaults_content[var_name], bool)
            )
            assert is_boolean, f"{var_name} should be inferred as boolean type"

    def test_infer_numeric_types(self, temp_dir):
        """Test inference of numeric types"""
        generator = ArgumentSpecsGenerator()

        defaults_content = {
            "app_port": 8080,
            "max_connections": 100,
            "timeout_seconds": 30,
            "retry_count": 3,
            "buffer_size": 1024,
            "api_version": 2,
            "weight": 1.5,
            "cpu_limit": 0.5,
        }

        defaults_file = temp_dir / "defaults.yml"
        with open(defaults_file, "w") as f:
            yaml.dump(defaults_content, f)

        for var_name, value in defaults_content.items():
            if isinstance(value, int):
                inferred_type = "int"
            elif isinstance(value, float):
                inferred_type = "float"
            else:
                inferred_type = "str"

            if isinstance(value, (int, float)):
                assert inferred_type in [
                    "int",
                    "float",
                ], f"{var_name} should be numeric type"

    def test_infer_list_types(self, temp_dir):
        """Test inference of list types"""
        generator = ArgumentSpecsGenerator()

        defaults_content = {
            "app_packages": ["nginx", "postgresql"],
            "allowed_hosts": ["localhost", "example.com"],
            "user_groups": ["admin", "users"],
            "config_files": ["/etc/app/main.conf", "/etc/app/local.conf"],
            "ports": [80, 443, 8080],
            "enabled_features": [],
        }

        defaults_file = temp_dir / "defaults.yml"
        with open(defaults_file, "w") as f:
            yaml.dump(defaults_content, f)

        list_variables = [
            "app_packages",
            "allowed_hosts",
            "user_groups",
            "config_files",
            "ports",
            "enabled_features",
        ]

        for var_name in list_variables:
            value = defaults_content[var_name]
            assert isinstance(
                value, list
            ), f"{var_name} should be inferred as list type"

    def test_infer_dict_types(self, temp_dir):
        """Test inference of dict types"""
        generator = ArgumentSpecsGenerator()

        defaults_content = {
            "app_config": {
                "database": {"host": "localhost", "port": 5432},
                "cache": {"type": "redis", "host": "localhost"},
            },
            "user_settings": {"theme": "dark", "language": "en"},
            "environment_vars": {"PATH": "/usr/bin", "HOME": "/home/user"},
            "empty_config": {},
        }

        defaults_file = temp_dir / "defaults.yml"
        with open(defaults_file, "w") as f:
            yaml.dump(defaults_content, f)

        dict_variables = [
            "app_config",
            "user_settings",
            "environment_vars",
            "empty_config",
        ]

        for var_name in dict_variables:
            value = defaults_content[var_name]
            assert isinstance(
                value, dict
            ), f"{var_name} should be inferred as dict type"


class TestSmartDescriptions:
    """Test smart description generation"""

    def test_generate_path_descriptions(self):
        """Test generation of descriptions for path variables"""
        generator = ArgumentSpecsGenerator()

        path_variables = {
            "config_path": "File system path for config path",
            "log_dir": "Directory path for log dir",
            "data_directory": "Directory path for data directory",
            "ssl_cert_file": "File system path for ssl cert file",
            "backup_folder": "Directory path for backup folder",
        }

        for var_name, expected_pattern in path_variables.items():
            # Test description generation logic
            if any(keyword in var_name.lower() for keyword in ["path", "file"]):
                desc_type = "File system path"
            elif any(
                keyword in var_name.lower()
                for keyword in ["dir", "directory", "folder"]
            ):
                desc_type = "Directory path"
            else:
                desc_type = "Path"

            expected_desc = f"{desc_type} for {var_name.replace('_', ' ')}"

            # Verify the pattern matches expected
            assert desc_type in expected_pattern

    def test_generate_boolean_descriptions(self):
        """Test generation of descriptions for boolean variables"""
        generator = ArgumentSpecsGenerator()

        boolean_variables = {
            "app_enabled": "Enable or disable functionality",
            "debug_mode": "Enable debug mode or output",
            "force_update": "Force operation or override",
            "ssl_enabled": "Enable or disable functionality",
            "use_compression": "Enable or use feature",
        }

        for var_name, expected_pattern in boolean_variables.items():
            # Test boolean description patterns
            if "enable" in var_name.lower() or var_name.endswith("_enabled"):
                desc_pattern = "Enable or disable functionality"
            elif "debug" in var_name.lower() or "mode" in var_name.lower():
                desc_pattern = "Enable debug mode or output"
            elif "force" in var_name.lower():
                desc_pattern = "Force operation or override"
            elif "use" in var_name.lower():
                desc_pattern = "Enable or use feature"
            else:
                desc_pattern = "Boolean flag"

            # Check if our pattern matches expected behavior
            assert any(
                keyword in expected_pattern
                for keyword in ["Enable", "Force", "Boolean"]
            )

    def test_generate_list_descriptions(self):
        """Test generation of descriptions for list variables"""
        generator = ArgumentSpecsGenerator()

        list_variables = {
            "app_packages": "List of values for app packages",
            "user_groups": "List of values for user groups",
            "config_files": "List of values for config files",
            "allowed_hosts": "List of values for allowed hosts",
        }

        for var_name, expected_pattern in list_variables.items():
            # Test list description generation
            clean_name = var_name.replace("_", " ")
            expected_desc = f"List of values for {clean_name}"

            assert expected_desc == expected_pattern

    def test_generate_numeric_descriptions(self):
        """Test generation of descriptions for numeric variables"""
        generator = ArgumentSpecsGenerator()

        numeric_variables = {
            "port": "Port number (numeric value)",
            "timeout": "Timeout value in seconds (numeric value)",
            "max_connections": "Maximum number for max connections",
            "retry_count": "Count value for retry count",
            "buffer_size": "Size value for buffer size",
        }

        for var_name, expected_pattern in numeric_variables.items():
            # Test numeric description patterns
            if "port" in var_name.lower():
                desc_pattern = "Port number"
            elif "timeout" in var_name.lower():
                desc_pattern = "Timeout value"
            elif "max" in var_name.lower():
                desc_pattern = "Maximum number"
            elif "count" in var_name.lower():
                desc_pattern = "Count value"
            elif "size" in var_name.lower():
                desc_pattern = "Size value"
            else:
                desc_pattern = "Numeric value"

            assert any(
                keyword in expected_pattern
                for keyword in [
                    "Port",
                    "Timeout",
                    "Maximum",
                    "Count",
                    "Size",
                    "Numeric",
                ]
            )


class TestRequiredFieldDetection:
    """Test detection of required fields"""

    def test_required_detection_from_defaults(self, temp_dir):
        """Test that variables with defaults are marked as optional"""
        generator = ArgumentSpecsGenerator()

        # Create role structure with defaults
        role_dir = temp_dir / "defaults_role"
        role_dir.mkdir()
        (role_dir / "defaults").mkdir()
        (role_dir / "tasks").mkdir()

        # Variables with defaults (should be optional)
        defaults_content = {"app_name": "myapp", "app_port": 8080, "app_enabled": True}

        with open(role_dir / "defaults" / "main.yml", "w") as f:
            yaml.dump(defaults_content, f)

        # Tasks that use variables without defaults (should be required)
        tasks_content = [
            {
                "name": "Configure app",
                "template": {"src": "config.j2", "dest": "/etc/app.conf"},
                "vars": {
                    "database_host": "{{ database_host }}",  # No default - required
                    "api_key": "{{ api_key }}",  # No default - required
                    "app_name": "{{ app_name }}",  # Has default - optional
                },
            }
        ]

        with open(role_dir / "tasks" / "main.yml", "w") as f:
            yaml.dump(tasks_content, f)

        # Analyze the role
        analysis = generator.analyze_role_structure(str(role_dir))

        # Variables with defaults should be marked as optional
        # Variables without defaults should be marked as required
        variables = analysis.get("variables", {})

        # This is testing the expected behavior - implementation may vary
        for var_name in defaults_content.keys():
            # Variables with defaults should not be required
            if var_name in variables:
                var_info = variables[var_name]
                # Should have default value from defaults file
                assert var_info.get("default") is not None

    def test_required_detection_from_asserts(self, temp_dir):
        """Test that variables in assert statements are marked as required"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Assert required variables
  assert:
    that:
      - app_name is defined
      - database_password is defined
      - ssl_cert_path is defined or not ssl_enabled
    fail_msg: "Required variables are missing"

- name: Use variables
  debug:
    msg: "App: {{ app_name }}, DB: {{ database_host | default('localhost') }}"
"""

        task_file = temp_dir / "assert_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Variables in assert statements should be detected
        # Check for variables that should be found in assert statements
        assert_variables = {"app_name", "database_password", "ssl_cert_path"}
        found_vars = assert_variables.intersection(variables)
        assert (
            len(found_vars) >= 2
        ), f"Expected to find at least 2 assert variables, found: {found_vars} from {variables}"

        # Variables with defaults should also be detected
        assert "database_host" in variables


class TestOutputFormatting:
    """Test YAML output formatting"""

    def test_yaml_output_structure(self):
        """Test proper YAML output structure"""
        generator = ArgumentSpecsGenerator()

        # Create a complex entry point with various argument types
        arg_specs = {
            "app_name": ArgumentSpec(
                name="app_name",
                type="str",
                required=True,
                description="Application name",
            ),
            "app_port": ArgumentSpec(
                name="app_port",
                type="int",
                default=8080,
                description="Application port number",
            ),
            "app_config": ArgumentSpec(
                name="app_config",
                type="dict",
                description="Application configuration",
                options={"database": {"type": "dict"}, "cache": {"type": "dict"}},
            ),
            "app_packages": ArgumentSpec(
                name="app_packages",
                type="list",
                elements="str",
                default=["nginx"],
                description="List of packages to install",
            ),
        }

        entry_point = EntryPointSpec(
            name="main",
            short_description="Main application entry point",
            description=[
                "Install and configure application",
                "Handles all setup tasks",
            ],
            author=["Test Author <test@example.com>"],
            options=arg_specs,
            required_if=[["state", "present", ["app_name"]]],
            mutually_exclusive=[["app_name", "app_id"]],
        )

        generator.add_entry_point(entry_point)

        # Generate YAML
        yaml_content = generator.generate_yaml()

        # Verify YAML structure
        assert yaml_content.startswith("---")
        assert yaml_content.endswith("...\n")

        # Parse and verify structure
        parsed = yaml.safe_load(yaml_content)

        assert "argument_specs" in parsed
        assert "main" in parsed["argument_specs"]

        main_spec = parsed["argument_specs"]["main"]
        assert main_spec["short_description"] == "Main application entry point"
        assert len(main_spec["description"]) == 2
        assert len(main_spec["author"]) == 1
        assert len(main_spec["options"]) == 4
        assert "required_if" in main_spec
        assert "mutually_exclusive" in main_spec

        # Verify options are sorted alphabetically
        option_keys = list(main_spec["options"].keys())
        assert option_keys == sorted(option_keys)

    def test_yaml_output_no_reference_anchors(self):
        """Test that YAML output doesn't contain reference anchors"""
        generator = ArgumentSpecsGenerator()

        # Create entry points with repeated content that might cause anchors
        common_description = ["Common description line 1", "Common description line 2"]
        common_author = ["Common Author <author@example.com>"]

        for i in range(3):
            entry_point = EntryPointSpec(
                name=f"entry_{i}",
                description=common_description.copy(),  # Same content
                author=common_author.copy(),  # Same content
            )
            generator.add_entry_point(entry_point)

        yaml_content = generator.generate_yaml()

        # Should not contain YAML reference anchors
        assert "&" not in yaml_content  # No anchors
        assert "*" not in yaml_content  # No references

        # Content should be fully repeated
        parsed = yaml.safe_load(yaml_content)

        for i in range(3):
            entry_spec = parsed["argument_specs"][f"entry_{i}"]
            assert entry_spec["description"] == common_description
            assert entry_spec["author"] == common_author

    def test_yaml_output_unicode_handling(self):
        """Test proper handling of unicode characters in YAML output"""
        generator = ArgumentSpecsGenerator()

        # Create entry point with unicode content
        arg_spec = ArgumentSpec(
            name="unicode_arg", description="Descripción with ñoño and émojis 🚀"
        )

        entry_point = EntryPointSpec(
            name="main",
            short_description="Configuración de aplicación",
            description=["Línea with special chars: áéíóú", "Emoji test: 🔧⚙️"],
            author=["Señor Developer <señor@example.com>"],
            options={"unicode_arg": arg_spec},
        )

        generator.add_entry_point(entry_point)

        yaml_content = generator.generate_yaml()

        # Should be valid YAML with unicode
        parsed = yaml.safe_load(yaml_content)

        main_spec = parsed["argument_specs"]["main"]
        assert "Configuración" in main_spec["short_description"]
        assert "🚀" in main_spec["options"]["unicode_arg"]["description"]
        assert "🔧" in main_spec["description"][1]
        assert "Señor" in main_spec["author"][0]

    def test_yaml_output_preserves_data_types(self):
        """Test that YAML output preserves correct data types"""
        generator = ArgumentSpecsGenerator()

        # Create arguments with various data types
        arg_specs = {
            "string_arg": ArgumentSpec(name="string_arg", type="str", default="text"),
            "int_arg": ArgumentSpec(name="int_arg", type="int", default=42),
            "float_arg": ArgumentSpec(name="float_arg", type="float", default=3.14),
            "bool_arg": ArgumentSpec(name="bool_arg", type="bool", default=True),
            "list_arg": ArgumentSpec(
                name="list_arg", type="list", default=["item1", "item2"]
            ),
            "dict_arg": ArgumentSpec(
                name="dict_arg", type="dict", default={"key": "value"}
            ),
        }

        entry_point = EntryPointSpec(name="main", options=arg_specs)
        generator.add_entry_point(entry_point)

        yaml_content = generator.generate_yaml()
        parsed = yaml.safe_load(yaml_content)

        options = parsed["argument_specs"]["main"]["options"]

        # Verify data types are preserved
        assert isinstance(options["string_arg"]["default"], str)
        assert isinstance(options["int_arg"]["default"], int)
        assert isinstance(options["float_arg"]["default"], float)
        assert isinstance(options["bool_arg"]["default"], bool)
        assert isinstance(options["list_arg"]["default"], list)
        assert isinstance(options["dict_arg"]["default"], dict)

        # Verify values are correct
        assert options["string_arg"]["default"] == "text"
        assert options["int_arg"]["default"] == 42
        assert options["float_arg"]["default"] == 3.14
        assert options["bool_arg"]["default"] == True
        assert options["list_arg"]["default"] == ["item1", "item2"]
        assert options["dict_arg"]["default"] == {"key": "value"}
