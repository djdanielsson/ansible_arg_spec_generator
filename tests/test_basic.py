"""
Basic smoke tests for ansible-argument-spec-generator package

These are simple smoke tests to verify basic functionality.
For comprehensive testing, see the other test_*.py files.
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Try to import pytest, but don't fail if it's not available
try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    # Mock pytest.fail for standalone running
    class MockPytest:
        @staticmethod
        def fail(msg):
            raise AssertionError(msg)

    pytest = MockPytest()

# Import the main module
sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_argument_specs import ArgumentSpecsGenerator, ArgumentSpec, EntryPointSpec


def test_generator_initialization():
    """Test that the generator initializes correctly"""
    generator = ArgumentSpecsGenerator()
    assert generator is not None
    assert generator.verbosity == 0
    assert generator.entry_points == {}
    assert generator.processed_roles == []


def test_valid_role_variable():
    """Test variable validation function"""
    generator = ArgumentSpecsGenerator()

    # Valid variables
    assert generator._is_valid_role_variable("app_name") == True
    assert generator._is_valid_role_variable("database_host") == True
    assert generator._is_valid_role_variable("config_path") == True

    # Invalid variables (should be filtered out)
    assert generator._is_valid_role_variable("__private_var") == False
    assert generator._is_valid_role_variable("ansible_facts") == False
    assert generator._is_valid_role_variable("inventory_hostname") == False
    assert generator._is_valid_role_variable("item") == False


def test_argument_spec_creation():
    """Test basic ArgumentSpec creation"""
    spec = ArgumentSpec(
        name="test_arg", type="str", required=True, description="Test argument"
    )

    assert spec.name == "test_arg"
    assert spec.type == "str"
    assert spec.required == True
    assert spec.description == "Test argument"


def test_entry_point_spec_creation():
    """Test basic EntryPointSpec creation"""
    arg_spec = ArgumentSpec(name="test_arg", type="str")
    entry_point = EntryPointSpec(
        name="main",
        short_description="Test entry point",
        options={"test_arg": arg_spec},
    )

    assert entry_point.name == "main"
    assert entry_point.short_description == "Test entry point"
    assert "test_arg" in entry_point.options


def test_yaml_generation_basic():
    """Test basic YAML generation"""
    generator = ArgumentSpecsGenerator()

    # Add a simple entry point since generate_yaml() requires at least one
    entry_point = EntryPointSpec(
        name="main", short_description="Basic test entry point"
    )
    generator.add_entry_point(entry_point)

    # Test YAML generation
    yaml_content = generator.generate_yaml()
    assert "argument_specs:" in yaml_content
    assert "main:" in yaml_content
    assert yaml_content.startswith("---")
    assert yaml_content.endswith("...\n")


def test_add_entry_point():
    """Test adding entry points to generator"""
    generator = ArgumentSpecsGenerator()
    entry_point = EntryPointSpec(name="test_entry")

    generator.add_entry_point(entry_point)

    assert "test_entry" in generator.entry_points
    assert generator.entry_points["test_entry"] == entry_point


def test_logging_functionality():
    """Test basic logging functionality"""
    generator = ArgumentSpecsGenerator(verbosity=2)

    # Should not raise exceptions
    generator.log_info("Test info message")
    generator.log_verbose("Test verbose message")
    generator.log_debug("Test debug message")


def test_yaml_with_entry_point():
    """Test YAML generation with an entry point"""
    generator = ArgumentSpecsGenerator()

    # Create a simple entry point
    arg_spec = ArgumentSpec(name="test_var", type="str", description="Test variable")

    entry_point = EntryPointSpec(
        name="main", short_description="Test role", options={"test_var": arg_spec}
    )

    generator.add_entry_point(entry_point)

    yaml_content = generator.generate_yaml()

    # Should contain the entry point
    assert "argument_specs:" in yaml_content
    assert "main:" in yaml_content
    assert "test_var:" in yaml_content


def test_package_import():
    """Test that the package can be imported correctly"""
    try:
        import generate_argument_specs

        assert hasattr(generate_argument_specs, "ArgumentSpecsGenerator")
        assert hasattr(generate_argument_specs, "ArgumentSpec")
        assert hasattr(generate_argument_specs, "EntryPointSpec")
        assert hasattr(generate_argument_specs, "main")
    except ImportError as e:
        pytest.fail(f"Failed to import package: {e}")


if __name__ == "__main__":
    # Run basic tests
    test_package_import()
    test_generator_initialization()
    test_argument_spec_creation()
    test_entry_point_spec_creation()
    test_yaml_generation_basic()
    test_add_entry_point()
    test_logging_functionality()
    test_valid_role_variable()
    test_yaml_with_entry_point()
    print("✅ All basic smoke tests passed!")
