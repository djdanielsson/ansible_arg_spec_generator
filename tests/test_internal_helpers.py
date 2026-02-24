"""
Tests for internal helper methods: _safe_load_yaml_file, _get_nested_value,
_merge_included_variables, _add_entry_point_variables, _create_entry_point_spec,
_analyze_task_files, _determine_entry_points, save_all_role_specs,
and variable context analysis methods.
"""

import os
import pytest
import yaml
from pathlib import Path

from generate_argument_specs import ArgumentSpecsGenerator, EntryPointSpec, ArgumentSpec


@pytest.fixture
def gen():
    return ArgumentSpecsGenerator(verbosity=0)


class TestSafeLoadYamlFile:
    """Test _safe_load_yaml_file method."""

    def test_valid_yaml(self, gen, temp_dir):
        f = temp_dir / "valid.yml"
        f.write_text(yaml.dump({"key": "value", "num": 42}))
        result = gen._safe_load_yaml_file(f)
        assert result == {"key": "value", "num": 42}

    def test_empty_file(self, gen, temp_dir):
        f = temp_dir / "empty.yml"
        f.touch()
        result = gen._safe_load_yaml_file(f)
        assert result == {}

    def test_whitespace_only_file(self, gen, temp_dir):
        f = temp_dir / "ws.yml"
        f.write_text("   \n  \n")
        result = gen._safe_load_yaml_file(f)
        assert result == {}

    def test_invalid_yaml(self, gen, temp_dir):
        f = temp_dir / "bad.yml"
        f.write_text("key: value\n  bad: {[")
        result = gen._safe_load_yaml_file(f)
        assert result is None

    def test_nonexistent_file(self, gen, temp_dir):
        f = temp_dir / "nope.yml"
        result = gen._safe_load_yaml_file(f)
        assert result is None

    def test_os_error(self, gen, temp_dir):
        d = temp_dir / "a_dir"
        d.mkdir()
        result = gen._safe_load_yaml_file(d)
        assert result is None


class TestGetNestedValue:
    """Test _get_nested_value method."""

    def test_simple_key(self, gen):
        assert gen._get_nested_value({"a": 1}, "a") == 1

    def test_nested_key(self, gen):
        data = {"a": {"b": {"c": 42}}}
        assert gen._get_nested_value(data, "a.b.c") == 42

    def test_missing_key(self, gen):
        assert gen._get_nested_value({"a": 1}, "b") is None

    def test_missing_nested_key(self, gen):
        assert gen._get_nested_value({"a": {"b": 1}}, "a.c") is None

    def test_non_dict_intermediate(self, gen):
        assert gen._get_nested_value({"a": "string"}, "a.b") is None

    def test_empty_data(self, gen):
        assert gen._get_nested_value({}, "a.b") is None


class TestAnalyzeTaskFiles:
    """Test _analyze_task_files method."""

    def test_no_tasks_dir(self, gen, temp_dir):
        role_dir = temp_dir / "norole"
        role_dir.mkdir()
        analysis = {
            "all_task_files": set(),
            "file_variables": {},
            "entry_points": {"main": {}},
        }
        gen._analyze_task_files(role_dir, analysis)
        assert analysis["all_task_files"] == set()

    def test_discovers_task_files(self, gen, temp_dir):
        role_dir = temp_dir / "role"
        tasks = role_dir / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "main.yml").write_text("---\n- name: t\n  debug:\n    msg: hi\n")
        (tasks / "install.yml").write_text("---\n- name: i\n  debug:\n    msg: hi\n")

        analysis = {
            "all_task_files": set(),
            "file_variables": {},
            "entry_points": {
                "main": {"variables": {}, "description": "", "short_description": ""}
            },
        }
        gen._analyze_task_files(role_dir, analysis)
        assert "main" in analysis["all_task_files"]
        assert "install" in analysis["all_task_files"]


class TestDetermineEntryPoints:
    """Test _determine_entry_points method."""

    def test_main_only(self, gen, temp_dir):
        tasks = temp_dir / "tasks"
        tasks.mkdir()
        main_file = tasks / "main.yml"
        main_file.write_text("---\n- name: t\n  include_tasks: helpers.yml\n")
        helper_file = tasks / "helpers.yml"
        helper_file.write_text("---\n- name: h\n  debug:\n    msg: hi\n")

        analysis = {
            "entry_points": {
                "main": {"variables": {}, "description": "", "short_description": ""}
            },
            "has_entry_points": False,
        }
        gen._determine_entry_points([main_file, helper_file], {"helpers"}, analysis)
        assert "helpers" not in analysis["entry_points"]

    def test_standalone_entry_points(self, gen, temp_dir):
        tasks = temp_dir / "tasks"
        tasks.mkdir()
        main_file = tasks / "main.yml"
        main_file.write_text("---\n- name: m\n  debug:\n    msg: hi\n")
        standalone = tasks / "backup.yml"
        standalone.write_text("---\n- name: b\n  debug:\n    msg: hi\n")

        analysis = {
            "entry_points": {
                "main": {"variables": {}, "description": "", "short_description": ""}
            },
            "has_entry_points": False,
        }
        gen._determine_entry_points([main_file, standalone], set(), analysis)
        assert "backup" in analysis["entry_points"]
        assert analysis["has_entry_points"] is True


class TestMergeIncludedVariables:
    """Test _merge_included_variables method."""

    def test_merges_variables_from_included_files(self, gen):
        ep = EntryPointSpec(name="main")
        analysis = {
            "file_includes_map": {"main": {"install"}},
            "file_variables": {"install": {"pkg_name", "pkg_version"}},
            "defaults": {},
            "vars": {},
            "version": "1.0.0",
        }
        gen._merge_included_variables(ep, "main", analysis)
        assert "pkg_name" in ep.options
        assert "pkg_version" in ep.options

    def test_does_not_override_existing_options(self, gen):
        ep = EntryPointSpec(name="main")
        ep.options["pkg_name"] = ArgumentSpec(
            name="pkg_name", description="Original desc"
        )
        analysis = {
            "file_includes_map": {"main": {"install"}},
            "file_variables": {"install": {"pkg_name"}},
            "defaults": {},
            "vars": {},
            "version": "1.0.0",
        }
        gen._merge_included_variables(ep, "main", analysis)
        assert ep.options["pkg_name"].description == "Original desc"

    def test_recursive_includes(self, gen):
        ep = EntryPointSpec(name="main")
        analysis = {
            "file_includes_map": {"main": {"a"}, "a": {"b"}, "b": set()},
            "file_variables": {"a": {"var_a"}, "b": {"var_b"}},
            "defaults": {},
            "vars": {},
            "version": "1.0.0",
        }
        gen._merge_included_variables(ep, "main", analysis)
        assert "var_a" in ep.options
        assert "var_b" in ep.options

    def test_circular_includes_handled(self, gen):
        ep = EntryPointSpec(name="main")
        analysis = {
            "file_includes_map": {"main": {"a"}, "a": {"b"}, "b": {"a"}},
            "file_variables": {"a": {"va"}, "b": {"vb"}},
            "defaults": {},
            "vars": {},
            "version": "1.0.0",
        }
        gen._merge_included_variables(ep, "main", analysis)
        assert "va" in ep.options
        assert "vb" in ep.options


class TestAddEntryPointVariables:
    """Test _add_entry_point_variables method."""

    def test_adds_variables_from_entry_point_file(self, gen):
        ep = EntryPointSpec(name="main")
        analysis = {
            "file_variables": {"main": {"ep_var1", "ep_var2"}},
            "defaults": {},
            "vars": {},
            "version": "1.0.0",
        }
        gen._add_entry_point_variables(ep, "main", analysis)
        assert "ep_var1" in ep.options
        assert "ep_var2" in ep.options

    def test_skips_existing_options(self, gen):
        ep = EntryPointSpec(name="main")
        ep.options["ep_var1"] = ArgumentSpec(name="ep_var1", description="Existing")
        analysis = {
            "file_variables": {"main": {"ep_var1"}},
            "defaults": {},
            "vars": {},
            "version": "1.0.0",
        }
        gen._add_entry_point_variables(ep, "main", analysis)
        assert ep.options["ep_var1"].description == "Existing"

    def test_marks_as_optional_if_has_default(self, gen):
        ep = EntryPointSpec(name="main")
        analysis = {
            "file_variables": {"main": {"my_var"}},
            "defaults": {"my_var": "default_val"},
            "vars": {},
            "version": "1.0.0",
        }
        gen._add_entry_point_variables(ep, "main", analysis)
        assert ep.options["my_var"].required is False


class TestVariableContextAnalysis:
    """Test variable context analysis methods."""

    def test_store_variable_context(self, gen):
        gen._store_variable_context(
            "my_var", {"context": "test", "module": "copy", "parameter": "src"}
        )
        assert "my_var" in gen.variable_context
        assert "copy_src" in gen.variable_context["my_var"]

    def test_store_multiple_contexts(self, gen):
        gen._store_variable_context(
            "my_var", {"context": "src", "module": "copy", "parameter": "src"}
        )
        gen._store_variable_context(
            "my_var", {"context": "dest", "module": "file", "parameter": "path"}
        )
        assert len(gen.variable_context["my_var"]) == 2

    def test_extract_variables_from_value_string(self, gen):
        result = gen._extract_variables_from_value("{{ my_var }}")
        assert "my_var" in result

    def test_extract_variables_from_value_with_filter(self, gen):
        result = gen._extract_variables_from_value("{{ my_var | default('x') }}")
        assert "my_var" in result

    def test_extract_variables_from_value_non_string(self, gen):
        assert gen._extract_variables_from_value(42) == []
        assert gen._extract_variables_from_value(None) == []

    def test_analyze_content_patterns(self, gen, temp_dir):
        content = 'dest: "/tmp/{{ dest_var }}"\nsrc: "{{ src_var }}/file"\nport: {{ port_var }}\n'
        gen._analyze_content_patterns(content, Path("test.yml"))
        assert "dest_var" in gen.variable_context
        assert "src_var" in gen.variable_context
        assert "port_var" in gen.variable_context

    def test_analyze_task_modules_copy(self, gen):
        task = {"copy": {"src": "{{ src_file }}", "dest": "{{ dest_file }}"}}
        gen._analyze_task_modules(task, Path("test.yml"))
        assert "src_file" in gen.variable_context
        assert "dest_file" in gen.variable_context

    def test_analyze_task_modules_service(self, gen):
        task = {"service": {"name": "{{ svc_name }}", "state": "{{ svc_state }}"}}
        gen._analyze_task_modules(task, Path("test.yml"))
        assert "svc_name" in gen.variable_context
        assert "svc_state" in gen.variable_context

    def test_analyze_task_modules_non_dict_params(self, gen):
        task = {"command": "echo hello"}
        gen._analyze_task_modules(task, Path("test.yml"))
        assert len(gen.variable_context) == 0

    def test_analyze_variable_usage_context_valid_yaml(self, gen, temp_dir):
        content = yaml.dump(
            [{"name": "t", "copy": {"src": "{{ my_src }}", "dest": "/tmp/x"}}]
        )
        gen._analyze_variable_usage_context(content, Path("test.yml"))
        assert "my_src" in gen.variable_context

    def test_analyze_variable_usage_context_invalid_yaml(self, gen, temp_dir):
        content = "not: valid: yaml: {["
        gen._analyze_variable_usage_context(content, Path("test.yml"))

    def test_analyze_variable_usage_context_non_list(self, gen, temp_dir):
        content = yaml.dump({"key": "value"})
        gen._analyze_variable_usage_context(content, Path("test.yml"))


class TestSaveAllRoleSpecs:
    """Test save_all_role_specs method."""

    def test_save_all_role_specs(self, sample_collection_structure):
        gen = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        gen.process_collection(str(sample_collection_structure))

        for role in gen.processed_roles:
            specs = (
                sample_collection_structure
                / "roles"
                / role
                / "meta"
                / "argument_specs.yml"
            )
            specs.unlink(missing_ok=True)

        gen.save_all_role_specs(str(sample_collection_structure))

        for role in gen.processed_roles:
            specs = (
                sample_collection_structure
                / "roles"
                / role
                / "meta"
                / "argument_specs.yml"
            )
            assert specs.exists()


class TestAnalyzeRoleStructureErrors:
    """Test analyze_role_structure error paths."""

    def test_nonexistent_path(self, gen):
        with pytest.raises(FileNotFoundError):
            gen.analyze_role_structure("/nonexistent/path")

    def test_not_a_directory(self, gen, temp_dir):
        f = temp_dir / "afile.txt"
        f.write_text("hi")
        with pytest.raises(NotADirectoryError):
            gen.analyze_role_structure(str(f))


class TestLogError:
    """Test log_error output."""

    def test_log_error_always_shown(self, capsys):
        gen = ArgumentSpecsGenerator(verbosity=0)
        gen.log_error("Something went wrong")
        captured = capsys.readouterr()
        assert "Something went wrong" in captured.out

    def test_log_error_with_role_prefix(self, capsys):
        gen = ArgumentSpecsGenerator(verbosity=0)
        gen.current_role = "myrole"
        gen.log_error("fail")
        captured = capsys.readouterr()
        assert "[myrole]" in captured.out
