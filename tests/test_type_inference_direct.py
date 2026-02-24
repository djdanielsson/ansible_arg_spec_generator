"""
Direct tests for type inference mixin methods:
_infer_argument_spec, _infer_list_element_type, _infer_string_type,
_generate_smart_description, _format_description_by_type, _generate_fallback_description.
"""

import pytest

from generate_argument_specs import ArgumentSpecsGenerator, ArgumentSpec


@pytest.fixture
def gen():
    return ArgumentSpecsGenerator(verbosity=0)


class TestInferArgumentSpec:
    """Test _infer_argument_spec method directly."""

    def test_bool_value(self, gen):
        spec = gen._infer_argument_spec("flag", True)
        assert spec.type == "bool"
        assert spec.default is True

    def test_int_value(self, gen):
        spec = gen._infer_argument_spec("port", 8080)
        assert spec.type == "int"
        assert spec.default == 8080

    def test_float_value(self, gen):
        spec = gen._infer_argument_spec("ratio", 0.75)
        assert spec.type == "float"
        assert spec.default == 0.75

    def test_list_value(self, gen):
        spec = gen._infer_argument_spec("packages", ["a", "b"])
        assert spec.type == "list"
        assert spec.elements == "str"

    def test_dict_value(self, gen):
        spec = gen._infer_argument_spec("config", {"k": "v"})
        assert spec.type == "dict"

    def test_string_value(self, gen):
        spec = gen._infer_argument_spec("name", "myapp")
        assert spec.type == "str"
        assert spec.default == "myapp"

    def test_none_value(self, gen):
        spec = gen._infer_argument_spec("unknown", None)
        assert spec.type == "str"

    def test_existing_description_preserved(self, gen):
        spec = gen._infer_argument_spec(
            "port", 80, existing_description="My custom desc"
        )
        assert spec.description == "My custom desc"

    def test_existing_version_preserved(self, gen):
        spec = gen._infer_argument_spec(
            "port", 80, existing_version_added="1.0.0"
        )
        assert spec.version_added == "1.0.0"

    def test_new_variable_gets_version(self, gen):
        spec = gen._infer_argument_spec(
            "port", 80, is_existing=False, current_version="2.0.0"
        )
        assert spec.version_added == "2.0.0"

    def test_existing_variable_no_version(self, gen):
        spec = gen._infer_argument_spec(
            "port", 80, is_existing=True, current_version="2.0.0"
        )
        assert spec.version_added is None

    def test_path_string_inference(self, gen):
        spec = gen._infer_argument_spec("config_path", "/etc/app/config.yml")
        assert spec.type == "path"


class TestInferListElementType:
    """Test _infer_list_element_type method."""

    def test_empty_list(self, gen):
        assert gen._infer_list_element_type([]) == "str"

    def test_str_elements(self, gen):
        assert gen._infer_list_element_type(["a", "b", "c"]) == "str"

    def test_int_elements(self, gen):
        assert gen._infer_list_element_type([1, 2, 3]) == "int"

    def test_dict_elements(self, gen):
        assert gen._infer_list_element_type([{"k": "v"}]) == "dict"

    def test_float_elements(self, gen):
        assert gen._infer_list_element_type([1.0, 2.5]) == "float"

    def test_bool_elements(self, gen):
        # Python's bool is a subclass of int, so Counter groups them together
        result = gen._infer_list_element_type([True, False])
        assert result in ("int", "bool")

    def test_mixed_elements_most_common_wins(self, gen):
        result = gen._infer_list_element_type(["a", "b", "c", 1])
        assert result == "str"


class TestInferStringType:
    """Test _infer_string_type method."""

    def test_path_keyword_with_path_value(self, gen):
        assert gen._infer_string_type("config_path", "/etc/app") == "path"

    def test_dir_keyword(self, gen):
        assert gen._infer_string_type("log_dir", "/var/log") == "path"

    def test_directory_keyword(self, gen):
        assert gen._infer_string_type("data_directory", "/var/data") == "path"

    def test_file_keyword(self, gen):
        assert gen._infer_string_type("cert_file", "/etc/ssl/cert.pem") == "path"

    def test_location_keyword(self, gen):
        assert gen._infer_string_type("install_location", "/usr/local") == "path"

    def test_path_keyword_non_path_value(self, gen):
        assert gen._infer_string_type("config_path", "relative") == "str"

    def test_url_keyword(self, gen):
        assert gen._infer_string_type("api_url", "https://example.com") == "str"

    def test_state_keyword(self, gen):
        assert gen._infer_string_type("state", "present") == "str"

    def test_generic_string(self, gen):
        assert gen._infer_string_type("app_name", "myapp") == "str"


class TestGenerateSmartDescription:
    """Test _generate_smart_description method."""

    def test_variable_context_used(self, gen):
        gen.variable_context["my_var"] = {
            "copy_src": {
                "context": "source file path",
                "module": "copy",
                "parameter": "src",
            }
        }
        desc = gen._generate_smart_description("my_var", "/path", "str")
        assert "source file path" in desc
        assert "copy" in desc

    def test_exact_pattern_match(self, gen):
        desc = gen._generate_smart_description("port", 8080, "int")
        assert "Port" in desc

    def test_partial_pattern_match(self, gen):
        desc = gen._generate_smart_description("app_port", 8080, "int")
        assert "Port" in desc or "port" in desc.lower()

    def test_fallback_description(self, gen):
        desc = gen._generate_smart_description("xyzzy_foobar", "val", "str")
        assert len(desc) > 0

    def test_enable_pattern(self, gen):
        desc = gen._generate_smart_description("enable", True, "bool")
        assert "Enable" in desc or "enable" in desc.lower()

    def test_timeout_pattern(self, gen):
        desc = gen._generate_smart_description("timeout", 30, "int")
        assert "Timeout" in desc or "timeout" in desc.lower()


class TestFormatDescriptionByType:
    """Test _format_description_by_type method."""

    def test_bool_enabled(self, gen):
        result = gen._format_description_by_type("Feature toggle", True, "bool")
        assert "enabled by default" in result

    def test_bool_disabled(self, gen):
        result = gen._format_description_by_type("Feature toggle", False, "bool")
        assert "disabled by default" in result

    def test_int_value(self, gen):
        result = gen._format_description_by_type("Port", 8080, "int")
        assert "8080" in result

    def test_float_value(self, gen):
        result = gen._format_description_by_type("Ratio", 0.5, "float")
        assert "0.5" in result

    def test_empty_list(self, gen):
        result = gen._format_description_by_type("Items", [], "list")
        assert "empty by default" in result

    def test_single_item_list(self, gen):
        result = gen._format_description_by_type("Items", ["one"], "list")
        assert "default item" in result

    def test_multi_item_list(self, gen):
        result = gen._format_description_by_type("Items", ["a", "b", "c"], "list")
        assert "3 default items" in result

    def test_empty_dict(self, gen):
        result = gen._format_description_by_type("Config", {}, "dict")
        assert "empty by default" in result

    def test_non_empty_dict(self, gen):
        result = gen._format_description_by_type("Config", {"k": "v"}, "dict")
        assert "default configuration" in result

    def test_empty_string(self, gen):
        result = gen._format_description_by_type("Name", "", "str")
        assert "empty by default" in result

    def test_short_string(self, gen):
        result = gen._format_description_by_type("Name", "myapp", "str")
        assert "myapp" in result

    def test_long_string(self, gen):
        long_val = "x" * 60
        result = gen._format_description_by_type("Name", long_val, "str")
        assert "configured with default value" in result

    def test_none_value(self, gen):
        result = gen._format_description_by_type("Base", None, "str")
        assert result == "Base"


class TestGenerateFallbackDescription:
    """Test _generate_fallback_description method."""

    def test_list_suffix(self, gen):
        result = gen._generate_fallback_description("app_list", [], "list")
        assert "List of" in result

    def test_items_suffix(self, gen):
        result = gen._generate_fallback_description("package_items", [], "list")
        assert "List of" in result

    def test_config_suffix(self, gen):
        result = gen._generate_fallback_description("app_config", {}, "dict")
        assert "Configuration settings" in result

    def test_enabled_suffix(self, gen):
        result = gen._generate_fallback_description("feature_enabled", True, "bool")
        assert "Enable" in result

    def test_disabled_suffix(self, gen):
        result = gen._generate_fallback_description("feature_disabled", False, "bool")
        assert "Disable" in result

    def test_is_prefix(self, gen):
        result = gen._generate_fallback_description("is_active", True, "bool")
        assert "Whether to" in result

    def test_has_prefix(self, gen):
        result = gen._generate_fallback_description("has_ssl", True, "bool")
        assert "Whether to" in result

    def test_bool_fallback(self, gen):
        result = gen._generate_fallback_description("xyzzy", True, "bool")
        assert "Boolean flag" in result

    def test_int_fallback(self, gen):
        result = gen._generate_fallback_description("xyzzy", 42, "int")
        assert "Numeric value" in result

    def test_list_type_fallback(self, gen):
        result = gen._generate_fallback_description("xyzzy", [], "list")
        assert "List of" in result

    def test_dict_type_fallback(self, gen):
        result = gen._generate_fallback_description("xyzzy", {}, "dict")
        assert "Configuration dictionary" in result

    def test_path_type_fallback(self, gen):
        result = gen._generate_fallback_description("xyzzy", "/tmp", "path")
        assert "File system path" in result

    def test_str_type_fallback(self, gen):
        result = gen._generate_fallback_description("xyzzy", "val", "str")
        assert "Configuration value" in result
