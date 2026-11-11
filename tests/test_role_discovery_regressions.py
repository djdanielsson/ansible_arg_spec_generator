"""Defaults and include discovery must match the files Ansible actually loads."""

import textwrap

import pytest

from generate_argument_specs import ArgumentSpecsGenerator


def write_files(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_sibling_defaults_and_vars_are_not_automatically_loaded(tmp_path):
    write_files(
        tmp_path,
        {
            "defaults/main.yml": "app_port: 80\n",
            "defaults/unused.yml": "app_port: 9000\nunused_value: hello\n",
            "vars/main.yml": "app_state: present\n",
            "vars/unused.yml": "app_state: absent\nunused_internal: hello\n",
            "tasks/main.yml": "[]\n",
        },
    )
    gen = ArgumentSpecsGenerator(include_vars=True, collection_mode=False)
    gen.process_single_role(str(tmp_path))
    opts = gen.entry_points["main"].options
    assert set(opts) == {"app_port", "app_state"}
    assert opts["app_port"].default == 80
    assert opts["app_state"].default == "present"


@pytest.mark.parametrize("main_name", ["main.yml", "main.yaml", "main.json", "main"])
def test_supported_main_names(tmp_path, main_name):
    write_files(
        tmp_path, {"defaults/" + main_name: '{"app_port": 80}', "tasks/main.yml": "[]"}
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(tmp_path))
    assert gen.entry_points["main"].options["app_port"].default == 80


def test_main_directory_loads_nested_supported_files_in_order(tmp_path):
    write_files(
        tmp_path,
        {
            "defaults/main/00_nested/values.yml": "app_port: 80\napp_enabled: true\n",
            "defaults/main/10_override.yaml": "app_port: 8080\n",
            "defaults/main/20_values.json": '{"app_workers": 4}',
            "defaults/main/30_extensionless": "app_name: hello\n",
            "defaults/main/.hidden.yml": "app_port: 9000\n",
            "defaults/main/ignored.txt": "app_port: 9001\n",
            "defaults/main/backup.yml~": "app_port: 9002\n",
            "defaults/unselected.yml": "app_port: 9003\n",
            "tasks/main.yml": "[]",
        },
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(tmp_path))
    opts = gen.entry_points["main"].options
    assert set(opts) == {"app_port", "app_enabled", "app_workers", "app_name"}
    assert opts["app_port"].default == 8080
    assert opts["app_workers"].type == "int"


def test_main_yml_takes_precedence_over_yaml_and_directory(tmp_path):
    write_files(
        tmp_path,
        {
            "defaults/main.yml": "app_port: 80\n",
            "defaults/main.yaml": "app_port: 81\n",
            "defaults/main/extra.yml": "app_port: 82\n",
            "tasks/main.yml": "[]",
        },
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(tmp_path))
    assert gen.entry_points["main"].options["app_port"].default == 80


def test_nested_includes_keep_paths_and_resolve_relative_to_parent(tmp_path):
    write_files(
        tmp_path,
        {
            "tasks/main.yml": """
            - include_tasks: first/setup.yml
            - include_tasks: second/setup.yml
        """,
            "tasks/first/setup.yml": """
            - ansible.builtin.import_tasks:
                file: child.yml
            - debug:
                msg: "{{ first_input }}"
        """,
            "tasks/first/child.yml": '- debug:\n    msg: "{{ child_input }}"\n',
            "tasks/second/setup.yml": '- debug:\n    msg: "{{ second_input }}"\n',
        },
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(tmp_path))
    assert set(gen.entry_points) == {"main"}
    assert set(gen.entry_points["main"].options) == {
        "first_input",
        "second_input",
        "child_input",
    }
    analysis = gen.analyze_role_structure(str(tmp_path))
    assert analysis["file_includes_map"]["main"] == {"first/setup", "second/setup"}
    assert analysis["file_includes_map"]["first/setup"] == {"first/child"}


def test_mixed_top_level_and_block_fqcn_includes(tmp_path):
    write_files(
        tmp_path,
        {
            "tasks/main.yml": """
            - include_tasks: first.yml
            - block:
                - ansible.builtin.include_tasks: second.yml
              rescue:
                - ansible.builtin.import_tasks: rescue.yml
              always:
                - ansible.builtin.include_tasks:
                    file: always.yml
        """,
            "tasks/first.yml": '- debug:\n    msg: "{{ first_input }}"\n',
            "tasks/second.yml": '- debug:\n    msg: "{{ second_input }}"\n',
            "tasks/rescue.yml": '- debug:\n    msg: "{{ rescue_input }}"\n',
            "tasks/always.yml": '- debug:\n    msg: "{{ always_input }}"\n',
        },
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(tmp_path))
    assert set(gen.entry_points) == {"main"}
    assert set(gen.entry_points["main"].options) == {
        "first_input",
        "second_input",
        "rescue_input",
        "always_input",
    }


def test_cycles_terminate_without_losing_other_dependencies(tmp_path):
    write_files(
        tmp_path,
        {
            "tasks/main.yml": "- include_tasks: nested/child.yml\n",
            "tasks/nested/child.yml": """
            - include_tasks: ../main.yml
            - debug:
                msg: "{{ app_name }}"
        """,
        },
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(tmp_path))
    assert set(gen.entry_points["main"].options) == {"app_name"}


def test_dynamic_includes_are_not_misidentified_as_literal_paths(tmp_path):
    write_files(
        tmp_path, {"tasks/main.yml": '- include_tasks: "{{ app_task_file }}.yml"\n'}
    )
    gen = ArgumentSpecsGenerator(collection_mode=False)
    assert gen.parse_task_file_includes(tmp_path / "tasks/main.yml") == set()
    gen.process_single_role(str(tmp_path))
    assert set(gen.entry_points["main"].options) == {"app_task_file"}
