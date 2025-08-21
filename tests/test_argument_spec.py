"""
Tests for ArgumentSpec and EntryPointSpec classes
"""

import pytest
from generate_argument_specs import ArgumentSpec, EntryPointSpec, ArgumentType


class TestArgumentSpec:
    """Test the ArgumentSpec dataclass"""

    def test_argument_spec_initialization(self):
        """Test basic ArgumentSpec initialization"""
        spec = ArgumentSpec(name="test_arg")
        assert spec.name == "test_arg"
        assert spec.type == "str"  # default
        assert spec.required == False  # default
        assert spec.default is None
        assert spec.description is None

    def test_argument_spec_with_all_fields(self):
        """Test ArgumentSpec with all fields populated"""
        spec = ArgumentSpec(
            name="complex_arg",
            type="dict",
            required=True,
            default={"key": "value"},
            choices=None,
            description="A complex argument",
            elements="str",
            options={"nested": {"type": "str"}},
            version_added="1.2.0",
        )

        assert spec.name == "complex_arg"
        assert spec.type == "dict"
        assert spec.required == True
        assert spec.default == {"key": "value"}
        assert spec.description == "A complex argument"
        assert spec.elements == "str"
        assert spec.options == {"nested": {"type": "str"}}
        assert spec.version_added == "1.2.0"

    def test_argument_spec_to_dict_minimal(self):
        """Test to_dict method with minimal data"""
        spec = ArgumentSpec(name="simple_arg")
        result = spec.to_dict()

        expected = {"type": "str"}
        assert result == expected

    def test_argument_spec_to_dict_complete(self):
        """Test to_dict method with complete data"""
        spec = ArgumentSpec(
            name="complete_arg",
            type="list",
            required=True,
            default=["item1", "item2"],
            choices=["choice1", "choice2", "choice3"],
            description="Complete argument spec",
            elements="str",
            version_added="1.1.0",
        )

        result = spec.to_dict()
        expected = {
            "description": "Complete argument spec",
            "type": "list",
            "required": True,
            "default": ["item1", "item2"],
            "choices": ["choice1", "choice2", "choice3"],
            "elements": "str",
            "version_added": "1.1.0",
        }
        assert result == expected

    def test_argument_spec_to_dict_excludes_none_values(self):
        """Test that to_dict excludes None values"""
        spec = ArgumentSpec(
            name="test_arg",
            type="str",
            required=False,  # Should not appear in output
            default=None,  # Should not appear in output
            choices=None,  # Should not appear in output
            description="Test description",
        )

        result = spec.to_dict()
        expected = {"description": "Test description", "type": "str"}
        assert result == expected
        assert "required" not in result  # False should not appear
        assert "default" not in result
        assert "choices" not in result

    def test_argument_spec_boolean_required(self):
        """Test that required=True appears in output"""
        spec = ArgumentSpec(name="required_arg", required=True)
        result = spec.to_dict()

        assert result["required"] == True
        assert "required" in result

    def test_argument_spec_default_false(self):
        """Test that default=False appears in output"""
        spec = ArgumentSpec(name="bool_arg", type="bool", default=False)
        result = spec.to_dict()

        assert result["default"] == False
        assert "default" in result

    def test_argument_spec_nested_options(self):
        """Test ArgumentSpec with nested options (for dict type)"""
        spec = ArgumentSpec(
            name="dict_arg",
            type="dict",
            options={
                "nested_key": {"type": "str", "required": True},
                "optional_key": {"type": "int", "default": 42},
            },
        )

        result = spec.to_dict()
        assert result["options"] == {
            "nested_key": {"type": "str", "required": True},
            "optional_key": {"type": "int", "default": 42},
        }


class TestEntryPointSpec:
    """Test the EntryPointSpec dataclass"""

    def test_entry_point_spec_initialization(self):
        """Test basic EntryPointSpec initialization"""
        spec = EntryPointSpec()
        assert spec.name == "main"  # default
        assert spec.short_description == ""
        assert spec.description == []  # initialized in __post_init__
        assert spec.author == []  # initialized in __post_init__
        assert spec.options == {}  # initialized in __post_init__

    def test_entry_point_spec_post_init(self):
        """Test __post_init__ method"""
        spec = EntryPointSpec(
            name="test_entry", description=None, author=None, options=None
        )

        # __post_init__ should initialize None values to empty collections
        assert spec.description == []
        assert spec.author == []
        assert spec.options == {}

    def test_entry_point_spec_with_data(self):
        """Test EntryPointSpec with data"""
        arg_spec = ArgumentSpec(name="test_arg", type="str", required=True)

        spec = EntryPointSpec(
            name="install",
            short_description="Install packages",
            description=["Install and configure packages", "Handles dependencies"],
            author=[
                "Author One <author1@example.com>",
                "Author Two <author2@example.com>",
            ],
            options={"test_arg": arg_spec},
        )

        assert spec.name == "install"
        assert spec.short_description == "Install packages"
        assert len(spec.description) == 2
        assert len(spec.author) == 2
        assert "test_arg" in spec.options

    def test_entry_point_spec_to_dict_minimal(self):
        """Test to_dict method with minimal data"""
        spec = EntryPointSpec()
        result = spec.to_dict()

        # Should be empty dict for minimal spec
        assert result == {}

    def test_entry_point_spec_to_dict_complete(self):
        """Test to_dict method with complete data"""
        arg_spec = ArgumentSpec(
            name="app_name", type="str", required=True, description="Application name"
        )

        spec = EntryPointSpec(
            name="main",
            short_description="Main entry point",
            description=["Deploy application", "Configure services"],
            author=["Test Author <test@example.com>"],
            options={"app_name": arg_spec},
            required_if=[["state", "present", ["app_name"]]],
            mutually_exclusive=[["app_name", "app_id"]],
        )

        result = spec.to_dict()

        assert result["short_description"] == "Main entry point"
        assert result["description"] == ["Deploy application", "Configure services"]
        assert result["author"] == ["Test Author <test@example.com>"]
        assert "app_name" in result["options"]
        assert result["required_if"] == [["state", "present", ["app_name"]]]
        assert result["mutually_exclusive"] == [["app_name", "app_id"]]

    def test_entry_point_spec_options_sorted_alphabetically(self):
        """Test that options are sorted alphabetically in output"""
        arg1 = ArgumentSpec(name="zebra_arg", type="str")
        arg2 = ArgumentSpec(name="alpha_arg", type="str")
        arg3 = ArgumentSpec(name="beta_arg", type="str")

        spec = EntryPointSpec(
            options={"zebra_arg": arg1, "alpha_arg": arg2, "beta_arg": arg3}
        )

        result = spec.to_dict()
        option_keys = list(result["options"].keys())

        # Should be sorted alphabetically
        assert option_keys == ["alpha_arg", "beta_arg", "zebra_arg"]

    def test_entry_point_spec_description_as_string(self):
        """Test description conversion from string to list"""
        spec = EntryPointSpec(description="Single string description")
        result = spec.to_dict()

        # String should be converted to list
        assert result["description"] == ["Single string description"]
        assert isinstance(result["description"], list)

    def test_entry_point_spec_description_list_copy(self):
        """Test that description list is copied (not referenced)"""
        original_desc = ["Line 1", "Line 2"]
        spec = EntryPointSpec(description=original_desc)
        result = spec.to_dict()

        # Modify original list
        original_desc.append("Line 3")

        # Result should not be affected
        assert result["description"] == ["Line 1", "Line 2"]
        assert len(result["description"]) == 2

    def test_entry_point_spec_author_list_copy(self):
        """Test that author list is copied (not referenced)"""
        original_authors = ["Author 1 <auth1@example.com>"]
        spec = EntryPointSpec(author=original_authors)
        result = spec.to_dict()

        # Modify original list
        original_authors.append("Author 2 <auth2@example.com>")

        # Result should not be affected
        assert result["author"] == ["Author 1 <auth1@example.com>"]
        assert len(result["author"]) == 1

    def test_entry_point_spec_conditional_requirements(self):
        """Test all conditional requirement types"""
        spec = EntryPointSpec(
            required_if=[["state", "present", ["app_name"]]],
            required_one_of=[["app_name", "app_id"]],
            mutually_exclusive=[["app_name", "app_id"]],
            required_together=[["ssl_cert", "ssl_key"]],
        )

        result = spec.to_dict()

        assert result["required_if"] == [["state", "present", ["app_name"]]]
        assert result["required_one_of"] == [["app_name", "app_id"]]
        assert result["mutually_exclusive"] == [["app_name", "app_id"]]
        assert result["required_together"] == [["ssl_cert", "ssl_key"]]

    def test_entry_point_spec_excludes_empty_conditionals(self):
        """Test that empty conditional requirements are excluded"""
        spec = EntryPointSpec(
            required_if=None,
            required_one_of=[],
            mutually_exclusive=None,
            required_together=[],
        )

        result = spec.to_dict()

        # None and empty lists should not appear in output
        assert "required_if" not in result
        assert "required_one_of" not in result
        assert "mutually_exclusive" not in result
        assert "required_together" not in result


class TestArgumentType:
    """Test the ArgumentType enum"""

    def test_argument_type_values(self):
        """Test ArgumentType enum values"""
        assert ArgumentType.STR.value == "str"
        assert ArgumentType.INT.value == "int"
        assert ArgumentType.FLOAT.value == "float"
        assert ArgumentType.BOOL.value == "bool"
        assert ArgumentType.LIST.value == "list"
        assert ArgumentType.DICT.value == "dict"
        assert ArgumentType.PATH.value == "path"
        assert ArgumentType.RAW.value == "raw"

    def test_argument_type_enum_members(self):
        """Test that all expected enum members exist"""
        expected_types = {"STR", "INT", "FLOAT", "BOOL", "LIST", "DICT", "PATH", "RAW"}
        actual_types = {member.name for member in ArgumentType}
        assert actual_types == expected_types
