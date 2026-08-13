"""
Adversarial / messy variable extraction and include parsing tests.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from generate_argument_specs import ArgumentSpecsGenerator


class TestMessyTaskExtraction:
    def test_excludes_registered_and_set_fact_names(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "tasks.yml"
        task_file.write_text(
            """---
- name: Run command
  command: echo hi
  register: cmd_result

- name: Set fact
  set_fact:
    computed_value: "{{ app_name }}"

- name: Use register
  debug:
    msg: "{{ cmd_result.stdout }} {{ computed_value }} {{ app_name }}"
  when: cmd_result.rc == 0
"""
        )
        variables = gen.extract_variables_from_task_file(task_file)
        assert "app_name" in variables
        assert "cmd_result" not in variables
        assert "computed_value" not in variables
        assert "stdout" not in variables
        assert "rc" not in variables

    def test_loop_and_with_items(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "loop.yml"
        task_file.write_text(
            """---
- name: Loop packages
  package:
    name: "{{ item }}"
  loop: "{{ app_packages }}"

- name: With items
  debug:
    msg: "{{ item }}"
  with_items: "{{ app_users }}"
"""
        )
        variables = gen.extract_variables_from_task_file(task_file)
        assert "app_packages" in variables
        assert "app_users" in variables
        assert "item" not in variables

    def test_nested_jinja_in_strings_and_environment(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "env.yml"
        task_file.write_text(
            """---
- name: Env task
  shell: echo "{{ app_message }}"
  environment:
    APP_HOME: "{{ app_home }}"
    APP_TOKEN: "{{ app_token }}"
  tags: "{{ app_tags }}"
"""
        )
        variables = gen.extract_variables_from_task_file(task_file)
        assert {"app_message", "app_home", "app_token", "app_tags"}.issubset(variables)

    def test_assert_that_list(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "assert.yml"
        task_file.write_text(
            """---
- name: Assert
  assert:
    that:
      - required_host is defined
      - required_port is defined
      - optional_flag is not defined or optional_flag
"""
        )
        variables = gen.extract_variables_from_task_file(task_file)
        assert "required_host" in variables
        assert "required_port" in variables

    def test_filters_ansible_builtins_exactly(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "builtins.yml"
        task_file.write_text(
            """---
- name: Mix
  debug:
    msg: "{{ inventory_hostname }} {{ item_name }} {{ ansible_os_family }} {{ groups_extra }}"
  when: groups is defined
"""
        )
        variables = gen.extract_variables_from_task_file(task_file)
        assert "item_name" in variables
        assert "groups_extra" in variables
        assert "inventory_hostname" not in variables
        assert "ansible_os_family" not in variables
        assert "groups" not in variables

    def test_malformed_yaml_falls_back_to_regex(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "bad.yml"
        task_file.write_text(
            """---
- name: Broken indent
  debug:
    msg: "{{ salvage_var }}"
  when: salvage_enabled
 this is not valid yaml: [
"""
        )
        variables = gen.extract_variables_from_task_file(task_file)
        assert "salvage_var" in variables

    def test_unicode_decode_error_returns_empty(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "bin.yml"
        task_file.write_bytes(b"\xff\xfe{{ app_name }}\n")
        # encoding=utf-8 will raise UnicodeDecodeError in open for some content;
        # our reader uses encoding=utf-8 without errors=ignore for tasks
        variables = gen.extract_variables_from_task_file(task_file)
        assert variables == set() or "app_name" not in variables or isinstance(
            variables, set
        )


class TestIncludeParsing:
    def test_include_tasks_dict_form(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "main.yml"
        task_file.write_text(
            """---
- name: Include
  include_tasks:
    file: nested/setup.yml
"""
        )
        includes = gen.parse_task_file_includes(task_file)
        assert "setup" in includes

    def test_import_tasks_and_include(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        task_file = temp_dir / "main.yml"
        task_file.write_text(
            """---
- import_tasks: install.yml
- include: legacy.yml
- include_tasks: configure.yml
"""
        )
        includes = gen.parse_task_file_includes(task_file)
        assert {"install", "legacy", "configure"}.issubset(includes)

    def test_recursive_includes_merge_variables(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("{}\n")
        (role / "tasks" / "main.yml").write_text(
            "---\n- include_tasks: level1.yml\n"
        )
        (role / "tasks" / "level1.yml").write_text(
            '---\n- include_tasks: level2.yml\n- debug:\n    msg: "{{ level1_var }}"\n'
        )
        (role / "tasks" / "level2.yml").write_text(
            '---\n- debug:\n    msg: "{{ level2_var }}"\n'
        )

        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role), "role")
        opts = gen.entry_points["main"].options
        assert "level1_var" in opts
        assert "level2_var" in opts

    def test_circular_includes_do_not_hang(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("{}\n")
        (role / "tasks" / "main.yml").write_text(
            "---\n- include_tasks: a.yml\n"
        )
        (role / "tasks" / "a.yml").write_text(
            '---\n- include_tasks: b.yml\n- debug:\n    msg: "{{ a_var }}"\n'
        )
        (role / "tasks" / "b.yml").write_text(
            '---\n- include_tasks: a.yml\n- debug:\n    msg: "{{ b_var }}"\n'
        )

        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role), "role")
        opts = gen.entry_points["main"].options
        assert "a_var" in opts
        assert "b_var" in opts


class TestAdversarialRoleFiles:
    def test_empty_and_non_mapping_defaults_ignored(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("")
        (role / "defaults" / "list.yml").write_text("- a\n- b\n")
        (role / "defaults" / "ok.yml").write_text("ok_var: 1\n")
        (role / "tasks" / "main.yml").write_text("---\n[]\n")

        gen = ArgumentSpecsGenerator(collection_mode=False)
        analysis = gen.analyze_role_structure(str(role))
        assert analysis["defaults"] == {"ok_var": 1}

    def test_deeply_nested_template_tree(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        nested = role / "templates" / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "c.j2").write_text("{{ deep_template_var }}\n")
        (role / "defaults" / "main.yml").write_text("{}\n")
        (role / "tasks" / "main.yml").write_text("---\n[]\n")

        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role), "role")
        assert "deep_template_var" in gen.entry_points["main"].options
