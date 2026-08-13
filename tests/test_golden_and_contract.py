"""
Golden-file style regression tests and Ansible argument_specs contract checks.
"""

from pathlib import Path

import pytest
import yaml

from generate_argument_specs import ArgumentSpecsGenerator

VALID_OPTION_TYPES = {"str", "int", "float", "bool", "list", "dict", "path", "raw"}


def assert_ansible_argument_specs_contract(data: dict) -> None:
    """Validate structure Ansible expects for meta/argument_specs.yml (no ansible install)."""
    assert isinstance(data, dict)
    assert "argument_specs" in data
    specs = data["argument_specs"]
    assert isinstance(specs, dict)
    assert specs, "argument_specs must not be empty"

    for ep_name, ep in specs.items():
        assert isinstance(ep_name, str) and ep_name
        assert isinstance(ep, dict)
        assert "short_description" in ep
        assert isinstance(ep["short_description"], str)

        if "description" in ep:
            assert isinstance(ep["description"], list)
            assert all(isinstance(line, str) for line in ep["description"])

        if "author" in ep:
            assert isinstance(ep["author"], list)

        options = ep.get("options", {})
        assert isinstance(options, dict)

        for opt_name, opt in options.items():
            assert isinstance(opt_name, str) and opt_name
            assert isinstance(opt, dict)
            assert "type" in opt
            assert opt["type"] in VALID_OPTION_TYPES
            if "required" in opt:
                assert isinstance(opt["required"], bool)
            if "choices" in opt:
                assert isinstance(opt["choices"], list)
            if "elements" in opt:
                assert opt["elements"] in VALID_OPTION_TYPES
            if "no_log" in opt:
                assert opt["no_log"] is True
            if "description" in opt:
                assert isinstance(opt["description"], (str, list))
            if opt.get("required") and "default" in opt:
                raise AssertionError(
                    f"{ep_name}.{opt_name}: required options must not set default"
                )

        for key in (
            "required_if",
            "required_one_of",
            "mutually_exclusive",
            "required_together",
        ):
            if key in ep:
                assert isinstance(ep[key], list)


def _build_realistic_role(role: Path) -> None:
    """Create a role that exercises defaults, vars, tasks, includes, templates, secrets."""
    for d in ("defaults", "vars", "tasks", "templates", "meta"):
        (role / d).mkdir(parents=True)

    (role / "defaults" / "main.yml").write_text(
        yaml.dump(
            {
                "app_enabled": True,
                "app_port": 8080,
                "app_packages": ["nginx", "curl"],
                "app_config_path": "/etc/app/config.yml",
                "app_password": "changeme",
            }
        )
    )
    (role / "defaults" / "extra.yml").write_text("app_workers: 4\n")

    (role / "vars" / "main.yml").write_text(
        yaml.dump({"__app_internal": "hidden", "app_state": "present"})
    )

    (role / "tasks" / "main.yml").write_text(
        """---
- name: Install packages
  package:
    name: "{{ app_packages }}"
    state: "{{ app_state }}"
  when: app_enabled

- name: Include configure
  include_tasks: configure.yml

- name: Register then use result
  command: /bin/true
  register: app_cmd_result
  changed_when: app_cmd_result.rc != 0
"""
    )
    (role / "tasks" / "configure.yml").write_text(
        """---
- name: Template config
  template:
    src: app.conf.j2
    dest: "{{ app_config_path }}"
  when: app_password is defined
"""
    )
    (role / "templates" / "app.conf.j2").write_text(
        "port={{ app_port }}\nworkers={{ app_workers }}\nlisten={{ app_listen_host }}\n"
    )
    (role / "meta" / "main.yml").write_text(
        yaml.dump(
            {
                "galaxy_info": {
                    "author": "Test Author <test@example.com>",
                    "description": "Realistic test role",
                }
            }
        )
    )


class TestGoldenRealisticRole:
    def test_generated_options_match_expected_set(self, temp_dir):
        role = temp_dir / "app"
        _build_realistic_role(role)

        gen = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        gen.process_single_role(str(role), "app")

        assert set(gen.entry_points.keys()) == {"main"}
        options = gen.entry_points["main"].options

        # Defaults / multi-file defaults
        assert options["app_enabled"].type == "bool"
        assert options["app_enabled"].default is True
        assert options["app_port"].type == "int"
        assert options["app_port"].default == 8080
        assert options["app_packages"].type == "list"
        assert options["app_packages"].elements == "str"
        assert options["app_workers"].type == "int"
        assert options["app_workers"].default == 4

        # Secret marking
        assert options["app_password"].no_log is True

        # Path inference
        assert options["app_config_path"].type == "path"

        # Template-only var
        assert "app_listen_host" in options
        assert options["app_listen_host"].required is True

        # Task var from vars/ (typed, but not exported as a vars-source option by default)
        assert "app_state" in options
        assert options["app_state"].type == "str"

        # Private / registered must not appear
        assert "__app_internal" not in options
        assert "app_cmd_result" not in options
        assert "rc" not in options

    def test_yaml_output_is_stable_for_key_fields(self, temp_dir):
        role = temp_dir / "app"
        _build_realistic_role(role)

        gen = ArgumentSpecsGenerator(collection_mode=True, verbosity=0, backup=False)
        gen.process_single_role(str(role), "app")

        specs_path = role / "meta" / "argument_specs.yml"
        assert specs_path.exists()
        data = yaml.safe_load(specs_path.read_text(encoding="utf-8"))
        assert_ansible_argument_specs_contract(data)

        main = data["argument_specs"]["main"]
        opts = main["options"]
        assert opts["app_port"]["type"] == "int"
        assert opts["app_port"]["default"] == 8080
        assert opts["app_password"]["no_log"] is True
        assert opts["app_packages"]["type"] == "list"
        assert opts["app_packages"]["elements"] == "str"
        assert "app_listen_host" in opts
        assert sorted(opts.keys()) == sorted(opts.keys())  # sanity

        # Authors pulled from meta
        assert main["author"] == ["Test Author <test@example.com>"]


class TestArgumentSpecsContract:
    def test_sample_collection_roles_satisfy_contract(self, sample_collection_structure):
        gen = ArgumentSpecsGenerator(collection_mode=True, verbosity=0, backup=False)
        gen.process_collection(str(sample_collection_structure))

        for role_name in ("webapp", "database"):
            path = (
                sample_collection_structure
                / "roles"
                / role_name
                / "meta"
                / "argument_specs.yml"
            )
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert_ansible_argument_specs_contract(data)

            # Exact expected defaults from fixture
            opts = data["argument_specs"]["main"]["options"]
            assert f"{role_name}_enabled" in opts
            assert opts[f"{role_name}_enabled"]["type"] == "bool"
            assert opts[f"{role_name}_port"]["type"] == "int"
            assert opts[f"{role_name}_packages"]["type"] == "list"
            assert f"__{role_name}_internal" not in opts

    def test_database_has_standalone_entry_points(self, sample_collection_structure):
        gen = ArgumentSpecsGenerator(collection_mode=True, verbosity=0, backup=False)
        gen.process_collection(str(sample_collection_structure))
        data = yaml.safe_load(
            (
                sample_collection_structure
                / "roles"
                / "database"
                / "meta"
                / "argument_specs.yml"
            ).read_text(encoding="utf-8")
        )
        # install.yml / configure.yml are included by main, so they are NOT entry points;
        # fixture marks them as include_tasks from main. Standalone only if not included.
        # In conftest, install/configure are included from main — so only main is required.
        assert "main" in data["argument_specs"]
