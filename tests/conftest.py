"""
pytest configuration and fixtures for ansible-argument-spec-generator tests
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any
import yaml

# Import main classes
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_argument_specs import ArgumentSpecsGenerator, ArgumentSpec, EntryPointSpec


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_collection_structure(temp_dir):
    """Create a sample collection structure for testing"""
    collection_dir = temp_dir / "sample_collection"
    collection_dir.mkdir()

    # Create galaxy.yml
    galaxy_content = {
        "namespace": "test",
        "name": "collection",
        "version": "1.2.0",
        "description": "Test collection",
        "authors": ["Test Author <test@example.com>"],
    }
    with open(collection_dir / "galaxy.yml", "w") as f:
        yaml.dump(galaxy_content, f)

    # Create roles directory
    roles_dir = collection_dir / "roles"
    roles_dir.mkdir()

    # Create webapp role
    webapp_role = roles_dir / "webapp"
    create_sample_role(webapp_role, "webapp")

    # Create database role
    database_role = roles_dir / "database"
    create_sample_role(database_role, "database", has_multiple_entry_points=True)

    return collection_dir


@pytest.fixture
def sample_single_role(temp_dir):
    """Create a sample single role for testing"""
    role_dir = temp_dir / "sample_role"
    create_sample_role(role_dir, "sample_role")
    return role_dir


def create_sample_role(
    role_dir: Path, role_name: str, has_multiple_entry_points: bool = False
):
    """Helper function to create a sample role structure"""
    role_dir.mkdir(parents=True, exist_ok=True)

    # Create directories
    (role_dir / "defaults").mkdir()
    (role_dir / "vars").mkdir()
    (role_dir / "tasks").mkdir()
    (role_dir / "meta").mkdir()

    # Create defaults/main.yml
    defaults_content = {
        f"{role_name}_enabled": True,
        f"{role_name}_port": 8080,
        f"{role_name}_config_path": f"/etc/{role_name}/config.yml",
        f"{role_name}_packages": ["package1", "package2"],
        f"{role_name}_debug": False,
    }
    with open(role_dir / "defaults" / "main.yml", "w") as f:
        yaml.dump(defaults_content, f)

    # Create vars/main.yml
    vars_content = {
        f"__{role_name}_internal": "internal_value",
        f"{role_name}_state": "present",
    }
    with open(role_dir / "vars" / "main.yml", "w") as f:
        yaml.dump(vars_content, f)

    # Create tasks/main.yml
    main_tasks = [
        {
            "name": f"Install {role_name} packages",
            "package": {
                "name": f"{{{{ {role_name}_packages }}}}",
                "state": f"{{{{ {role_name}_state }}}}",
            },
            "when": f"{role_name}_enabled",
        },
        {
            "name": f"Create {role_name} config directory",
            "file": {
                "path": f"{{{{ {role_name}_config_path | dirname }}}}",
                "state": "directory",
            },
        },
        {
            "name": f"Configure {role_name}",
            "template": {
                "src": "config.yml.j2",
                "dest": f"{{{{ {role_name}_config_path }}}}",
            },
            "notify": f"restart {role_name}",
        },
    ]

    if has_multiple_entry_points:
        main_tasks.extend(
            [
                {
                    "include_tasks": "install.yml",
                    "when": f"{role_name}_install_only is defined and {role_name}_install_only",
                },
                {
                    "include_tasks": "configure.yml",
                    "when": f"{role_name}_configure_only is defined and {role_name}_configure_only",
                },
            ]
        )

    with open(role_dir / "tasks" / "main.yml", "w") as f:
        yaml.dump(main_tasks, f)

    # Create additional task files if multiple entry points
    if has_multiple_entry_points:
        # tasks/install.yml
        install_tasks = [
            {
                "name": f"Install {role_name} packages only",
                "package": {
                    "name": f"{{{{ {role_name}_packages }}}}",
                    "state": "present",
                },
            }
        ]
        with open(role_dir / "tasks" / "install.yml", "w") as f:
            yaml.dump(install_tasks, f)

        # tasks/configure.yml
        configure_tasks = [
            {
                "name": f"Configure {role_name} only",
                "template": {
                    "src": "config.yml.j2",
                    "dest": f"{{{{ {role_name}_config_path }}}}",
                },
            }
        ]
        with open(role_dir / "tasks" / "configure.yml", "w") as f:
            yaml.dump(configure_tasks, f)

    # Create meta/main.yml
    meta_content = {
        "galaxy_info": {
            "author": f"{role_name.title()} Author",
            "description": f"A role to manage {role_name}",
            "license": "MIT",
            "min_ansible_version": "2.9",
            "platforms": [{"name": "Ubuntu", "versions": ["20.04", "22.04"]}],
        },
        "dependencies": [],
    }
    with open(role_dir / "meta" / "main.yml", "w") as f:
        yaml.dump(meta_content, f)


@pytest.fixture
def sample_argument_spec():
    """Create a sample ArgumentSpec for testing"""
    return ArgumentSpec(
        name="test_arg",
        type="str",
        required=True,
        default="default_value",
        description="Test argument description",
    )


@pytest.fixture
def sample_entry_point_spec():
    """Create a sample EntryPointSpec for testing"""
    arg_spec = ArgumentSpec(
        name="test_arg", type="str", required=True, description="Test argument"
    )

    return EntryPointSpec(
        name="main",
        short_description="Test entry point",
        description=["Test entry point description"],
        author=["Test Author <test@example.com>"],
        options={"test_arg": arg_spec},
    )


@pytest.fixture
def generator():
    """Create a basic ArgumentSpecsGenerator for testing"""
    return ArgumentSpecsGenerator(verbosity=0)


@pytest.fixture
def generator_verbose():
    """Create a verbose ArgumentSpecsGenerator for testing"""
    return ArgumentSpecsGenerator(verbosity=2)


@pytest.fixture
def mock_yaml_files(temp_dir):
    """Create mock YAML files with various edge cases"""
    files_dir = temp_dir / "yaml_files"
    files_dir.mkdir()

    # Valid YAML file
    valid_content = {"key": "value", "list": [1, 2, 3]}
    with open(files_dir / "valid.yml", "w") as f:
        yaml.dump(valid_content, f)

    # Invalid YAML file
    with open(files_dir / "invalid.yml", "w") as f:
        f.write("key: value\n  invalid_indentation: test\n")

    # Empty file
    (files_dir / "empty.yml").touch()

    # Non-existent file path (for testing)
    non_existent = files_dir / "non_existent.yml"

    return {
        "valid": files_dir / "valid.yml",
        "invalid": files_dir / "invalid.yml",
        "empty": files_dir / "empty.yml",
        "non_existent": non_existent,
    }


@pytest.fixture
def complex_task_content():
    """Sample complex task content for variable extraction testing"""
    return """
---
- name: Complex task with multiple variables
  package:
    name: "{{ app_packages | default(['nginx']) }}"
    state: "{{ app_state | default('present') }}"
  when: 
    - app_enabled | default(false)
    - ansible_os_family == "Debian"
  register: package_result

- name: Template configuration
  template:
    src: "{{ config_template | default('app.conf.j2') }}"
    dest: "{{ config_path }}/app.conf"
    owner: "{{ app_user | default('root') }}"
    group: "{{ app_group | default('root') }}"
    mode: "{{ config_mode | default('0644') }}"
  notify: restart application

- name: Assert required variables
  assert:
    that:
      - app_name is defined
      - app_version is defined
      - config_path is defined
    fail_msg: "Required variables are not defined"

- name: Debug information
  debug:
    var: package_result
  when: debug_mode | default(false)

- name: Include additional tasks
  include_tasks: "{{ additional_tasks_file }}"
  when: additional_tasks_file is defined
"""
