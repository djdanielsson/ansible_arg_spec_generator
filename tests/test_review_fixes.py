"""
Tests for review fixes: no_log, backups, include-vars, multi-file coverage,
quiet mode, validation gaps, preservation, and related CLI flags.
"""

import yaml
from pathlib import Path
from unittest.mock import patch

import pytest

from generate_argument_specs import (
    ArgumentSpecsGenerator,
    ArgumentSpec,
    EntryPointSpec,
    main,
)


class TestNoLogInference:
    def test_secret_names_get_no_log(self):
        gen = ArgumentSpecsGenerator()
        for name in ("db_password", "api_token", "client_secret", "access_key"):
            spec = gen._infer_argument_spec(name, "value")
            assert spec.no_log is True, name
            assert spec.to_dict().get("no_log") is True

    def test_non_secret_names_skip_no_log(self):
        gen = ArgumentSpecsGenerator()
        spec = gen._infer_argument_spec("app_port", 8080)
        assert not spec.no_log
        assert "no_log" not in spec.to_dict()


class TestBoolListElements:
    def test_bool_list_elements_inferred_as_bool(self):
        gen = ArgumentSpecsGenerator()
        assert gen._infer_list_element_type([True, False]) == "bool"
        assert gen._infer_list_element_type([1, 2, 3]) == "int"


class TestBuiltinFiltering:
    def test_exact_builtins_filtered_but_prefixes_allowed(self):
        gen = ArgumentSpecsGenerator()
        assert not gen._is_valid_role_variable("item")
        assert not gen._is_valid_role_variable("loop")
        assert not gen._is_valid_role_variable("groups")
        assert gen._is_valid_role_variable("item_name")
        assert gen._is_valid_role_variable("loopback")
        assert gen._is_valid_role_variable("groups_to_create")


class TestIncludeVarsOption:
    def test_vars_excluded_by_default(self, temp_dir):
        role = temp_dir / "role"
        role.mkdir()
        (role / "defaults").mkdir()
        (role / "vars").mkdir()
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("role_port: 80\n")
        (role / "vars" / "main.yml").write_text("role_internal_only: true\n")
        (role / "tasks" / "main.yml").write_text(
            '---\n- debug:\n    msg: "{{ role_port }}"\n'
        )

        gen = ArgumentSpecsGenerator(collection_mode=False, include_vars=False)
        gen.process_single_role(str(role), "role")
        assert "role_port" in gen.entry_points["main"].options
        assert "role_internal_only" not in gen.entry_points["main"].options

    def test_vars_included_when_flag_set(self, temp_dir):
        role = temp_dir / "role"
        role.mkdir()
        (role / "defaults").mkdir()
        (role / "vars").mkdir()
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("role_port: 80\n")
        (role / "vars" / "main.yml").write_text("role_internal_only: true\n")
        (role / "tasks" / "main.yml").write_text("---\n[]\n")

        gen = ArgumentSpecsGenerator(collection_mode=False, include_vars=True)
        gen.process_single_role(str(role), "role")
        assert "role_internal_only" in gen.entry_points["main"].options
        opt = gen.entry_points["main"].options["role_internal_only"]
        assert opt.type == "bool"
        assert opt.required is False


class TestBackup:
    def test_backup_created_by_default(self, temp_dir):
        out = temp_dir / "specs.yml"
        out.write_text("old: true\n")
        gen = ArgumentSpecsGenerator(backup=True)
        gen.add_entry_point(EntryPointSpec(name="main", short_description="New"))
        gen.save_to_file(str(out))
        backups = list(temp_dir.glob("specs.yml.*.bak"))
        assert len(backups) == 1
        assert "old: true" in backups[0].read_text()
        assert "argument_specs" in out.read_text()

    def test_no_backup_when_disabled(self, temp_dir):
        out = temp_dir / "specs.yml"
        out.write_text("old: true\n")
        gen = ArgumentSpecsGenerator(backup=False)
        gen.add_entry_point(EntryPointSpec(name="main", short_description="New"))
        gen.save_to_file(str(out))
        assert list(temp_dir.glob("specs.yml.*.bak")) == []


class TestMultiFileAndTemplates:
    def test_loads_additional_defaults_files(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("a: 1\n")
        (role / "defaults" / "extra.yml").write_text("b: 2\n")
        (role / "tasks" / "main.yml").write_text("---\n[]\n")

        gen = ArgumentSpecsGenerator(collection_mode=False)
        analysis = gen.analyze_role_structure(str(role))
        assert analysis["defaults"]["a"] == 1
        assert analysis["defaults"]["b"] == 2

    def test_extracts_template_variables(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "templates").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("{}\n")
        (role / "tasks" / "main.yml").write_text("---\n[]\n")
        (role / "templates" / "app.conf.j2").write_text(
            "listen {{ app_listen_port }}\nuser {{ app_user }}\n"
        )

        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role), "role")
        opts = gen.entry_points["main"].options
        assert "app_listen_port" in opts
        assert "app_user" in opts


class TestTaskVarTypes:
    def test_task_var_typed_from_defaults(self, temp_dir):
        role = temp_dir / "role"
        (role / "defaults").mkdir(parents=True)
        (role / "tasks").mkdir()
        (role / "meta").mkdir()
        (role / "defaults" / "main.yml").write_text("feature_flags: true\n")
        (role / "tasks" / "main.yml").write_text(
            '---\n- debug:\n    msg: "{{ feature_flags }}"\n'
        )
        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role), "role")
        assert gen.entry_points["main"].options["feature_flags"].type == "bool"


class TestQuietMode:
    def test_quiet_suppresses_summary(
        self, monkeypatch, sample_collection_structure, capsys
    ):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--quiet"]):
            main()
        captured = capsys.readouterr()
        assert "ARGUMENT SPECS GENERATION SUMMARY" not in captured.out
        assert "Successfully processed" not in captured.out


class TestExampleConfigPrompt:
    def test_prompt_abort_keeps_existing(self, temp_dir, monkeypatch):
        monkeypatch.chdir(temp_dir)
        existing = temp_dir / "example_config.yml"
        existing.write_text("keep: me\n")
        with patch("sys.argv", ["prog", "--create-example-config"]):
            with patch("builtins.input", return_value="n"):
                main()
        assert existing.read_text() == "keep: me\n"

    def test_prompt_yes_overwrites(self, temp_dir, monkeypatch):
        monkeypatch.chdir(temp_dir)
        existing = temp_dir / "example_config.yml"
        existing.write_text("keep: me\n")
        with patch("sys.argv", ["prog", "--create-example-config"]):
            with patch("builtins.input", return_value="y"):
                main()
        assert "entry_points" in existing.read_text()

    def test_quiet_refuses_overwrite(self, temp_dir, monkeypatch):
        monkeypatch.chdir(temp_dir)
        existing = temp_dir / "example_config.yml"
        existing.write_text("keep: me\n")
        with patch("sys.argv", ["prog", "--create-example-config", "--quiet"]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1
        assert existing.read_text() == "keep: me\n"


class TestValidationGaps:
    def test_required_with_default_invalid(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="x")
        ep.options["a"] = ArgumentSpec(name="a", required=True, default="x")
        gen.add_entry_point(ep)
        assert gen.validate_specs() is False

    def test_invalid_choices_type(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="x")
        ep.options["a"] = ArgumentSpec(name="a", choices="not-a-list")  # type: ignore
        gen.add_entry_point(ep)
        assert gen.validate_specs() is False

    def test_invalid_elements_type(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="x")
        ep.options["a"] = ArgumentSpec(name="a", type="list", elements="nope")
        gen.add_entry_point(ep)
        assert gen.validate_specs() is False

    def test_required_if_too_short(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="x")
        ep.options["state"] = ArgumentSpec(name="state")
        ep.required_if = [["state"]]
        gen.add_entry_point(ep)
        assert gen.validate_specs() is False

    def test_nested_options_validated(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="x")
        ep.options["cfg"] = ArgumentSpec(
            name="cfg",
            type="dict",
            options={"bad": {"type": "notatype"}},
        )
        gen.add_entry_point(ep)
        assert gen.validate_specs() is False


class TestFullPreservation:
    def test_preserves_choices_required_no_log_and_conditionals(self, temp_dir):
        role = temp_dir / "myrole"
        for d in ("defaults", "tasks", "meta"):
            (role / d).mkdir(parents=True)
        (role / "defaults" / "main.yml").write_text(
            "myrole_password: secret\nmyrole_state: present\n"
        )
        (role / "tasks" / "main.yml").write_text("---\n[]\n")
        existing = {
            "argument_specs": {
                "main": {
                    "short_description": "Custom",
                    "options": {
                        "myrole_password": {
                            "type": "str",
                            "description": "DB password",
                            "no_log": True,
                            "choices": None,
                        },
                        "myrole_state": {
                            "type": "str",
                            "description": "State",
                            "choices": ["present", "absent"],
                            "default": "present",
                        },
                        "manual_only": {
                            "type": "str",
                            "description": "Kept even if not rediscovered",
                            "required": True,
                        },
                    },
                    "mutually_exclusive": [["myrole_password", "manual_only"]],
                }
            }
        }
        (role / "meta" / "argument_specs.yml").write_text(yaml.dump(existing))

        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role), "myrole")
        ep = gen.entry_points["main"]
        assert ep.options["myrole_state"].choices == ["present", "absent"]
        assert ep.options["myrole_password"].no_log is True
        assert "manual_only" in ep.options
        assert ep.mutually_exclusive == [["myrole_password", "manual_only"]]


class TestCollectionFailureExit:
    def test_failed_role_raises(self, temp_dir):
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").write_text(
            yaml.dump({"namespace": "n", "name": "c", "version": "1.0.0"})
        )
        roles = coll / "roles"
        roles.mkdir()
        bad = roles / "bad"
        bad.mkdir()
        (bad / "tasks").mkdir()
        # analyze_role_structure succeeds on this; force failure via patch
        gen = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        with patch.object(
            gen, "process_single_role", side_effect=RuntimeError("boom")
        ):
            from generate_argument_specs import GeneratorError

            with pytest.raises(GeneratorError, match="failed"):
                gen.process_collection(str(coll))
