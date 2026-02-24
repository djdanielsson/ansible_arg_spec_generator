"""
Tests for ArgumentSpecsGenerator core functionality
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from generate_argument_specs import (
    ArgumentSpecsGenerator,
    ArgumentSpec,
    EntryPointSpec,
    GeneratorError,
    CollectionNotFoundError,
    ConfigError,
    ValidationError,
)


class TestArgumentSpecsGeneratorInit:
    """Test ArgumentSpecsGenerator initialization"""

    def test_generator_default_initialization(self):
        """Test default initialization"""
        generator = ArgumentSpecsGenerator()

        assert generator.collection_mode == True
        assert generator.verbosity == 0
        assert generator.current_role == ""
        assert generator.entry_points == {}
        assert generator.processed_roles == []
        assert generator.variable_context == {}
        assert generator.stats["roles_processed"] == 0

    def test_generator_custom_initialization(self):
        """Test initialization with custom parameters"""
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=2)

        assert generator.collection_mode == False
        assert generator.verbosity == 2

    def test_generator_add_entry_point(self):
        """Test adding entry points"""
        generator = ArgumentSpecsGenerator()
        entry_point = EntryPointSpec(name="test_entry")

        generator.add_entry_point(entry_point)

        assert "test_entry" in generator.entry_points
        assert generator.entry_points["test_entry"] == entry_point


class TestArgumentSpecsGeneratorLogging:
    """Test logging functionality"""

    def test_log_levels(self, capsys):
        """Test different log levels"""
        generator = ArgumentSpecsGenerator(verbosity=3)

        generator.log(1, "Info message")
        generator.log(2, "Verbose message")
        generator.log(3, "Debug message")
        generator.log(4, "Trace message")

        captured = capsys.readouterr()
        assert "Info message" in captured.out
        assert "Verbose message" in captured.out
        assert "Debug message" in captured.out
        assert "Trace message" not in captured.out  # Above verbosity level

    def test_log_with_role_prefix(self, capsys):
        """Test logging with role prefix"""
        generator = ArgumentSpecsGenerator(verbosity=2)
        generator.current_role = "test_role"

        generator.log(1, "Test message", role_prefix=True)

        captured = capsys.readouterr()
        assert "test_role" in captured.out
        assert "Test message" in captured.out

    def test_log_without_role_prefix(self, capsys):
        """Test logging without role prefix"""
        generator = ArgumentSpecsGenerator(verbosity=2)
        generator.current_role = "test_role"

        generator.log(1, "Test message", role_prefix=False)

        captured = capsys.readouterr()
        assert "test_role" not in captured.out
        assert "Test message" in captured.out

    def test_log_convenience_methods(self, capsys):
        """Test convenience logging methods"""
        generator = ArgumentSpecsGenerator(verbosity=3)

        generator.log_info("Info message")
        generator.log_verbose("Verbose message")
        generator.log_debug("Debug message")
        generator.log_trace("Trace message")
        generator.log_error("Error message")

        captured = capsys.readouterr()
        assert "Info message" in captured.out
        assert "Verbose message" in captured.out
        assert "Debug message" in captured.out
        assert "Error message" in captured.out

    def test_log_section(self, capsys):
        """Test section logging"""
        generator = ArgumentSpecsGenerator(verbosity=1)

        generator.log_section("Test Section")

        captured = capsys.readouterr()
        assert "Test Section" in captured.out
        assert "=" in captured.out  # Section separator


class TestArgumentSpecsGeneratorValidation:
    """Test variable validation functionality"""

    def test_is_valid_role_variable_valid_cases(self):
        """Test valid role variable names"""
        generator = ArgumentSpecsGenerator()

        valid_vars = [
            "app_name",
            "database_host",
            "config_path",
            "port_number",
            "enable_ssl",
            "package_list",
            "user_config",
            "timeout_seconds",
        ]

        for var_name in valid_vars:
            assert generator._is_valid_role_variable(
                var_name
            ), f"{var_name} should be valid"

    def test_is_valid_role_variable_invalid_cases(self):
        """Test invalid role variable names that should be filtered"""
        generator = ArgumentSpecsGenerator()

        invalid_vars = [
            "__private_var",  # Private variables
            "_internal_var",  # Internal variables
            "ansible_facts",  # Ansible built-ins
            "inventory_hostname",  # Ansible built-ins
            "hostvars",  # Ansible built-ins
            "group_names",  # Ansible built-ins
            "groups",  # Ansible built-ins
            "play_hosts",  # Ansible built-ins
            "item",  # Loop variables
            "ansible_loop",  # Loop variables
            "result.rc",  # Properties (contains dot)
            "result.stdout",  # Properties (contains dot)
            "result.stderr",  # Properties (contains dot)
            "task_result.changed",  # Properties (contains dot)
            "func()",  # Function calls
            "var[0]",  # Array access
            "123",  # Numeric values
            "a",  # Too short
            " ",  # Spaces
        ]

        for var_name in invalid_vars:
            assert not generator._is_valid_role_variable(
                var_name
            ), f"{var_name} should be invalid"

    def test_is_valid_role_variable_edge_cases(self):
        """Test edge cases for variable validation"""
        generator = ArgumentSpecsGenerator()

        # Empty string and None
        assert not generator._is_valid_role_variable("")
        assert not generator._is_valid_role_variable(None)

        # Very short variables (should be invalid - less than 2 chars)
        assert not generator._is_valid_role_variable("a")
        assert not generator._is_valid_role_variable("x")

        # Valid variables with numbers
        assert generator._is_valid_role_variable("var1")
        assert generator._is_valid_role_variable("app2_config")

        # Valid variables with underscores (but not starting with _)
        assert generator._is_valid_role_variable("var_name")
        assert generator._is_valid_role_variable("long_variable_name")

        # Invalid variables starting with underscore
        assert not generator._is_valid_role_variable("_private")
        assert not generator._is_valid_role_variable("__very_private")


class TestArgumentSpecsGeneratorCollectionDetection:
    """Test collection detection functionality"""

    def test_is_collection_root_valid(self, sample_collection_structure):
        """Test detection of valid collection root"""
        generator = ArgumentSpecsGenerator()

        # Test with valid collection
        assert generator.is_collection_root(str(sample_collection_structure))

    def test_is_collection_root_invalid(self, temp_dir):
        """Test detection of invalid collection root"""
        generator = ArgumentSpecsGenerator()

        # Test with directory without galaxy.yml
        invalid_dir = temp_dir / "not_a_collection"
        invalid_dir.mkdir()

        assert not generator.is_collection_root(str(invalid_dir))

    def test_is_collection_root_missing_roles(self, temp_dir):
        """Test collection root with galaxy.yml but no roles directory"""
        generator = ArgumentSpecsGenerator()

        # Create directory with galaxy.yml but no roles/
        partial_collection = temp_dir / "partial_collection"
        partial_collection.mkdir()

        galaxy_content = {"namespace": "test", "name": "test", "version": "1.0.0"}
        with open(partial_collection / "galaxy.yml", "w") as f:
            yaml.dump(galaxy_content, f)

        assert not generator.is_collection_root(str(partial_collection))

    def test_find_roles_in_collection(self, sample_collection_structure):
        """Test finding roles in a collection"""
        generator = ArgumentSpecsGenerator()

        roles = generator.find_roles(str(sample_collection_structure))

        assert len(roles) == 2
        assert "webapp" in roles
        assert "database" in roles

    def test_find_roles_empty_collection(self, temp_dir):
        """Test finding roles in collection with no roles"""
        generator = ArgumentSpecsGenerator()

        # Create collection with empty roles directory
        empty_collection = temp_dir / "empty_collection"
        empty_collection.mkdir()
        (empty_collection / "roles").mkdir()

        galaxy_content = {"namespace": "test", "name": "test", "version": "1.0.0"}
        with open(empty_collection / "galaxy.yml", "w") as f:
            yaml.dump(galaxy_content, f)

        roles = generator.find_roles(str(empty_collection))

        assert roles == []


class TestArgumentSpecsGeneratorYAMLGeneration:
    """Test YAML generation functionality"""

    def test_generate_yaml_empty(self):
        """Test YAML generation with no entry points returns empty specs"""
        generator = ArgumentSpecsGenerator()

        yaml_content = generator.generate_yaml()
        assert "argument_specs: {}" in yaml_content
        assert yaml_content.startswith("---")

    def test_generate_yaml_with_entry_points(self):
        """Test YAML generation with entry points"""
        generator = ArgumentSpecsGenerator()

        # Add an entry point with an argument
        arg_spec = ArgumentSpec(
            name="app_name", type="str", required=True, description="Application name"
        )

        entry_point = EntryPointSpec(
            name="main",
            short_description="Main entry point",
            options={"app_name": arg_spec},
        )

        generator.add_entry_point(entry_point)

        yaml_content = generator.generate_yaml()

        # Parse the generated YAML to verify structure
        parsed = yaml.safe_load(yaml_content)

        assert "argument_specs" in parsed
        assert "main" in parsed["argument_specs"]
        assert "options" in parsed["argument_specs"]["main"]
        assert "app_name" in parsed["argument_specs"]["main"]["options"]

        app_name_spec = parsed["argument_specs"]["main"]["options"]["app_name"]
        assert app_name_spec["type"] == "str"
        assert app_name_spec["required"] == True
        assert app_name_spec["description"] == "Application name"

    def test_generate_yaml_multiple_entry_points(self):
        """Test YAML generation with multiple entry points"""
        generator = ArgumentSpecsGenerator()

        # Add main entry point
        main_entry = EntryPointSpec(name="main", short_description="Main entry point")
        generator.add_entry_point(main_entry)

        # Add install entry point
        install_entry = EntryPointSpec(name="install", short_description="Install only")
        generator.add_entry_point(install_entry)

        yaml_content = generator.generate_yaml()
        parsed = yaml.safe_load(yaml_content)

        assert len(parsed["argument_specs"]) == 2
        assert "main" in parsed["argument_specs"]
        assert "install" in parsed["argument_specs"]

    def test_save_to_file(self, temp_dir):
        """Test saving YAML to file"""
        generator = ArgumentSpecsGenerator()

        # Add a simple entry point
        entry_point = EntryPointSpec(name="main", short_description="Test entry point")
        generator.add_entry_point(entry_point)

        # Save to file
        output_file = temp_dir / "test_argument_specs.yml"
        generator.save_to_file(str(output_file))

        # Verify file was created and contains expected content
        assert output_file.exists()

        with open(output_file, "r") as f:
            content = f.read()

        assert content.startswith("---")
        assert "argument_specs:" in content
        assert "main:" in content


class TestArgumentSpecsGeneratorUtilities:
    """Test utility methods"""

    def test_log_summary_empty(self, capsys):
        """Test summary logging with no processed roles"""
        generator = ArgumentSpecsGenerator(verbosity=1)

        generator.log_summary()

        captured = capsys.readouterr()
        assert "ARGUMENT SPECS GENERATION SUMMARY" in captured.out
        assert "Roles processed: 0" in captured.out
        assert "Entry points created: 0" in captured.out

    def test_log_summary_with_data(self, capsys):
        """Test summary logging with processed roles"""
        generator = ArgumentSpecsGenerator(verbosity=1)

        # Add some mock data
        generator.processed_roles = ["role1", "role2", "role3"]

        # Update stats to match what log_summary expects
        generator.stats["roles_processed"] = 3
        generator.stats["entry_points_created"] = 2
        generator.stats["total_variables"] = 10
        generator.stats["new_variables"] = 5
        generator.stats["existing_variables"] = 5

        # Add entry points to simulate processed data
        entry1 = EntryPointSpec(name="main")
        entry2 = EntryPointSpec(name="install")
        generator.add_entry_point(entry1)
        generator.add_entry_point(entry2)

        generator.log_summary()

        captured = capsys.readouterr()
        assert "Roles processed: 3" in captured.out
        assert "Entry points created: 2" in captured.out


class TestArgumentSpecsGeneratorErrorHandling:
    """Test error handling in various scenarios"""

    def test_yaml_generation_with_special_characters(self):
        """Test YAML generation handles special characters properly"""
        generator = ArgumentSpecsGenerator()

        # Create argument with special characters in description
        arg_spec = ArgumentSpec(
            name="special_arg",
            description="Description with 'quotes' and \"double quotes\" and unicode: ñoño",
        )

        entry_point = EntryPointSpec(name="main", options={"special_arg": arg_spec})

        generator.add_entry_point(entry_point)

        # Should not raise an exception
        yaml_content = generator.generate_yaml()

        # Should be valid YAML
        parsed = yaml.safe_load(yaml_content)
        assert parsed is not None

    def test_empty_role_path_handling(self):
        """Test handling of empty or invalid role paths"""
        generator = ArgumentSpecsGenerator()

        # Should handle empty path gracefully
        assert not generator.is_collection_root("")

        # Should handle non-existent path gracefully
        assert not generator.is_collection_root("/non/existent/path")

        # Should return empty list for invalid collection path
        roles = generator.find_roles("/non/existent/path")
        assert roles == []
