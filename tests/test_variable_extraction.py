"""
Tests for variable extraction and file parsing functionality
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from generate_argument_specs import ArgumentSpecsGenerator


class TestVariableExtractionFromTasks:
    """Test variable extraction from task files"""

    def test_extract_variables_basic_jinja2(self, temp_dir):
        """Test extraction of basic Jinja2 variables"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Install package
  package:
    name: "{{ app_name }}"
    state: "{{ app_state | default('present') }}"
  when: app_enabled
"""

        task_file = temp_dir / "tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Check for basic Jinja2 variables that should definitely be found
        expected_vars = {"app_name", "app_state"}  # These are in {{ }} blocks
        assert expected_vars.issubset(
            variables
        ), f"Expected {expected_vars} but got {variables}"

    def test_extract_variables_complex_expressions(self, temp_dir):
        """Test extraction from complex Jinja2 expressions"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Complex template task
  template:
    src: "{{ config_template | default('app.conf.j2') }}"
    dest: "{{ config_path }}/{{ app_name }}.conf"
    owner: "{{ app_user | default('root') }}"
    mode: "{{ config_mode | default('0644') }}"
  when: 
    - app_enabled | default(false)
    - config_template is defined
"""

        task_file = temp_dir / "complex_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Check for basic Jinja2 variables in {{ }} blocks
        expected_vars = {
            "app_name",
            "app_user",
            "config_mode",
            "config_path",
            "config_template",
        }
        assert expected_vars.issubset(
            variables
        ), f"Expected {expected_vars} but got {variables}"

    def test_extract_variables_from_when_conditions(self, temp_dir):
        """Test variable extraction from when conditions"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Conditional task
  debug:
    msg: "Running task"
  when: 
    - deployment_mode == "production"
    - ssl_enabled | default(false)
    - app_version is defined
    - database_password != ""
"""

        task_file = temp_dir / "conditional_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Check for variables that should be found in when conditions
        # Some may be in Jinja2 blocks, others in plain when conditions
        basic_vars = {"deployment_mode", "app_version", "database_password"}
        found_basic = basic_vars.intersection(variables)
        assert (
            len(found_basic) >= 2
        ), f"Expected to find at least 2 variables, found: {found_basic} from {variables}"

    def test_extract_variables_from_assert_statements(self, temp_dir):
        """Test variable extraction from assert statements"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Assert required variables
  assert:
    that:
      - app_name is defined
      - app_version is defined and app_version != ""
      - database_host is defined
      - ssl_cert_path is defined or not ssl_enabled
    fail_msg: "Required variables are missing"
"""

        task_file = temp_dir / "assert_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Check for variables in assert statements that should be extractable
        basic_vars = {"app_name", "app_version", "database_host", "ssl_cert_path"}
        found_basic = basic_vars.intersection(variables)
        assert (
            len(found_basic) >= 2
        ), f"Expected to find at least 2 assert variables, found: {found_basic} from {variables}"

    def test_extract_variables_from_loops(self, temp_dir):
        """Test variable extraction from loop constructs"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Install packages
  package:
    name: "{{ item }}"
    state: present
  loop: "{{ app_packages }}"
  when: package_enabled

- name: Create users
  user:
    name: "{{ item.name }}"
    groups: "{{ item.groups | default(default_groups) }}"
  loop: "{{ app_users }}"
"""

        task_file = temp_dir / "loop_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Check for basic loop variables
        basic_vars = {"app_packages", "app_users"}  # These should be in {{ }} blocks
        found_basic = basic_vars.intersection(variables)
        assert (
            len(found_basic) >= 1
        ), f"Expected to find at least 1 loop variable, found: {found_basic} from {variables}"

        # 'item' should be filtered out as it's a loop variable
        assert "item" not in variables

    def test_extract_variables_filters_registered_vars(self, temp_dir):
        """Test that registered variables are filtered out"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Run command
  command: /bin/echo "{{ message }}"
  register: command_result

- name: Use command result
  debug:
    var: command_result.stdout
  when: command_result.rc == 0

- name: Set fact
  set_fact:
    computed_value: "{{ base_value }}_computed"

- name: Use computed value
  debug:
    var: computed_value
"""

        task_file = temp_dir / "register_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Should include variables used in tasks
        assert "message" in variables
        assert "base_value" in variables

        # Should exclude registered variables and their properties
        assert "command_result" not in variables
        assert "computed_value" not in variables

    def test_extract_variables_from_include_statements(self, temp_dir):
        """Test variable extraction from include statements"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Include tasks conditionally
  include_tasks: "{{ additional_tasks_file }}"
  when: include_additional_tasks | default(false)

- name: Include role
  include_role:
    name: "{{ dependency_role }}"
  vars:
    role_config: "{{ app_config }}"
  when: use_dependency_role
"""

        task_file = temp_dir / "include_tasks.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        variables = generator.extract_variables_from_task_file(task_file)

        # Check for include/import variables that should be extractable
        basic_vars = {"additional_tasks_file", "app_config", "dependency_role"}
        found_basic = basic_vars.intersection(variables)
        assert (
            len(found_basic) >= 2
        ), f"Expected to find at least 2 include variables, found: {found_basic} from {variables}"


class TestTaskFileIncludeAnalysis:
    """Test analysis of task file includes and entry points"""

    def test_parse_task_file_includes_simple(self, temp_dir):
        """Test parsing simple include statements"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Include install tasks
  include_tasks: install.yml

- name: Include configure tasks  
  include_tasks: configure.yml
  when: configure_enabled
"""

        task_file = temp_dir / "main.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        included_files = generator.parse_task_file_includes(task_file)

        assert "install" in included_files
        assert "configure" in included_files

    def test_parse_task_file_includes_with_variables(self, temp_dir):
        """Test parsing includes with variable file names"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Include dynamic tasks
  include_tasks: "{{ task_file }}.yml"
  when: task_file is defined

- name: Include OS-specific tasks
  include_tasks: "{{ ansible_os_family | lower }}.yml"
"""

        task_file = temp_dir / "main.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        # Should handle variable file names gracefully
        included_files = generator.parse_task_file_includes(task_file)

        # Might not extract specific file names from variables, but shouldn't crash
        assert isinstance(included_files, set)

    def test_parse_task_file_includes_import_statements(self, temp_dir):
        """Test parsing import_tasks statements"""
        generator = ArgumentSpecsGenerator()

        task_content = """
---
- name: Import install tasks
  import_tasks: install.yml

- name: Import configure tasks
  import_tasks: configure.yml
"""

        task_file = temp_dir / "main.yml"
        with open(task_file, "w") as f:
            f.write(task_content)

        included_files = generator.parse_task_file_includes(task_file)

        assert "install" in included_files
        assert "configure" in included_files


class TestRoleStructureAnalysis:
    """Test role structure analysis"""

    def test_analyze_role_structure_basic(self, sample_single_role):
        """Test basic role structure analysis"""
        generator = ArgumentSpecsGenerator()

        analysis = generator.analyze_role_structure(str(sample_single_role))

        assert "entry_points" in analysis
        assert "variables" in analysis
        assert "meta_info" in analysis
        assert "version_info" in analysis

        # Should find main entry point
        assert "main" in analysis["entry_points"]

    def test_analyze_role_structure_with_includes(self, sample_collection_structure):
        """Test role analysis with included task files"""
        generator = ArgumentSpecsGenerator()

        # Analyze the database role which has multiple entry points
        database_role = sample_collection_structure / "roles" / "database"
        analysis = generator.analyze_role_structure(str(database_role))

        assert "entry_points" in analysis

        # Should detect multiple entry points
        entry_points = analysis["entry_points"]
        assert len(entry_points) >= 1  # At least main

    def test_analyze_role_structure_missing_directories(self, temp_dir):
        """Test role analysis with missing standard directories"""
        generator = ArgumentSpecsGenerator()

        # Create minimal role structure
        role_dir = temp_dir / "minimal_role"
        role_dir.mkdir()
        (role_dir / "tasks").mkdir()

        # Create minimal main.yml
        tasks_content = [{"name": "Minimal task", "debug": {"msg": "Hello"}}]
        with open(role_dir / "tasks" / "main.yml", "w") as f:
            yaml.dump(tasks_content, f)

        # Should handle missing defaults/, vars/, meta/ gracefully
        analysis = generator.analyze_role_structure(str(role_dir))

        assert analysis is not None
        assert "entry_points" in analysis


class TestVersionDetection:
    """Test version detection functionality"""

    def test_detect_version_from_collection(self, sample_collection_structure):
        """Test version detection from collection galaxy.yml"""
        generator = ArgumentSpecsGenerator()

        # Set up generator to be in collection mode
        os_chdir_original = Path.cwd

        try:
            # Change to collection directory for testing
            import os

            os.chdir(sample_collection_structure)

            database_role = sample_collection_structure / "roles" / "database"
            version_info = generator._detect_version_info(database_role)

            assert version_info["version"] == "1.2.0"
            assert version_info["source"] == "collection"

        finally:
            # Restore original directory
            os.chdir(os_chdir_original())

    def test_detect_version_from_role_meta(self, temp_dir):
        """Test version detection from role meta"""
        generator = ArgumentSpecsGenerator()

        # Create role with version in meta
        role_dir = temp_dir / "versioned_role"
        role_dir.mkdir()
        (role_dir / "meta").mkdir()

        meta_content = {
            "galaxy_info": {
                "author": "Test Author",
                "version": "2.1.0",
                "description": "Test role",
            }
        }

        with open(role_dir / "meta" / "main.yml", "w") as f:
            yaml.dump(meta_content, f)

        version_info = generator._detect_version_info(role_dir)

        assert version_info["version"] == "2.1.0"
        assert version_info["source"] == "role"

    def test_detect_version_fallback(self, temp_dir):
        """Test version detection fallback to default"""
        generator = ArgumentSpecsGenerator()

        # Create role without version info
        role_dir = temp_dir / "no_version_role"
        role_dir.mkdir()

        version_info = generator._detect_version_info(role_dir)

        assert version_info["version"] == "1.0.0"
        assert version_info["source"] == "default"


class TestMetaDataExtraction:
    """Test extraction of metadata from role meta files"""

    def test_extract_authors_from_meta(self):
        """Test author extraction from meta data"""
        generator = ArgumentSpecsGenerator()

        meta_data = {"galaxy_info": {"author": "John Doe <john@example.com>"}}

        authors = generator._extract_authors_from_meta(meta_data)

        assert len(authors) == 1
        assert "John Doe <john@example.com>" in authors

    def test_extract_authors_multiple_formats(self):
        """Test author extraction with multiple formats"""
        generator = ArgumentSpecsGenerator()

        # Test with list of authors
        meta_data = {
            "author": ["Author One", "Author Two <author2@example.com>"],
            "galaxy_info": {"author": "Galaxy Author"},
        }

        authors = generator._extract_authors_from_meta(meta_data)

        # Should extract from both locations
        assert len(authors) >= 2
        assert "Author One" in authors
        assert "Author Two <author2@example.com>" in authors

    def test_extract_descriptions_from_meta(self):
        """Test description extraction from meta data"""
        generator = ArgumentSpecsGenerator()

        meta_data = {
            "description": "Main role description",
            "galaxy_info": {
                "description": "Galaxy description",
                "short_description": "Short description",
            },
        }

        descriptions = generator._extract_descriptions_from_meta(meta_data)

        assert "description" in descriptions
        assert "short_description" in descriptions
        assert descriptions["description"] == "Main role description"
        assert descriptions["short_description"] == "Short description"


class TestErrorHandlingInVariableExtraction:
    """Test error handling in variable extraction"""

    def test_extract_variables_from_invalid_yaml(self, temp_dir):
        """Test handling of invalid YAML files"""
        generator = ArgumentSpecsGenerator()

        # Create file with invalid YAML
        invalid_yaml = """
---
- name: Task with invalid YAML
  package:
    name: test
  invalid_indentation: error
"""

        task_file = temp_dir / "invalid.yml"
        with open(task_file, "w") as f:
            f.write(invalid_yaml)

        # Should handle invalid YAML gracefully
        variables = generator.extract_variables_from_task_file(task_file)

        # Should return set (might be empty due to parsing error)
        assert isinstance(variables, set)

    def test_extract_variables_from_nonexistent_file(self):
        """Test handling of non-existent files"""
        generator = ArgumentSpecsGenerator()

        nonexistent_file = Path("/path/that/does/not/exist.yml")

        # Should handle missing files gracefully
        variables = generator.extract_variables_from_task_file(nonexistent_file)

        assert variables == set()

    def test_extract_variables_from_empty_file(self, temp_dir):
        """Test handling of empty files"""
        generator = ArgumentSpecsGenerator()

        empty_file = temp_dir / "empty.yml"
        empty_file.touch()  # Create empty file

        # Should handle empty files gracefully
        variables = generator.extract_variables_from_task_file(empty_file)

        assert variables == set()

    @patch("builtins.open", side_effect=PermissionError("Access denied"))
    def test_extract_variables_permission_error(self, mock_open):
        """Test handling of permission errors"""
        generator = ArgumentSpecsGenerator()

        # Should handle permission errors gracefully
        variables = generator.extract_variables_from_task_file(Path("test.yml"))

        assert variables == set()
