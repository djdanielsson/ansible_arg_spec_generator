"""
Tests for core generator methods: process_collection, process_single_role,
load_existing_specs, validate_specs, from_defaults_file, from_config_file.
"""

import json
import os
import pytest
import yaml
from pathlib import Path

from generate_argument_specs import (
    ArgumentSpecsGenerator,
    ArgumentSpec,
    ArgumentType,
    EntryPointSpec,
    ConfigError,
)


class TestProcessCollection:
    """Test process_collection method directly."""

    def test_process_collection_creates_specs_files(self, sample_collection_structure):
        generator = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        generator.process_collection(str(sample_collection_structure))

        assert generator.stats["roles_processed"] >= 2
        assert generator.stats["entry_points_created"] >= 2
        assert "webapp" in generator.processed_roles
        assert "database" in generator.processed_roles

        for role_name in generator.processed_roles:
            specs_file = (
                sample_collection_structure
                / "roles"
                / role_name
                / "meta"
                / "argument_specs.yml"
            )
            assert specs_file.exists(), f"Missing specs for {role_name}"
            content = yaml.safe_load(specs_file.read_text())
            assert "argument_specs" in content

    def test_process_collection_handles_failing_role(self, temp_dir):
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
        (bad / "tasks" / "main.yml").write_text(
            "---\n- name: t\n  debug:\n    msg: hi\n"
        )

        generator = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        generator.process_collection(str(coll))
        assert generator.stats["roles_processed"] >= 1


class TestProcessSingleRole:
    """Test process_single_role method directly."""

    def test_process_single_role_creates_entry_points(self, sample_single_role):
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        generator.process_single_role(str(sample_single_role), "sample_role")

        assert len(generator.entry_points) >= 1
        assert "main" in generator.entry_points
        main_ep = generator.entry_points["main"]
        assert len(main_ep.options) > 0

    def test_process_single_role_sets_current_role(self, sample_single_role):
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        generator.process_single_role(str(sample_single_role))
        assert generator.current_role == sample_single_role.name

    def test_process_single_role_infers_role_name(self, sample_single_role):
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        generator.process_single_role(str(sample_single_role))
        assert generator.current_role == sample_single_role.name

    def test_process_single_role_updates_stats(self, sample_single_role):
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        generator.process_single_role(str(sample_single_role), "sample_role")
        assert generator.stats["entry_points_created"] >= 1
        assert generator.stats["total_variables"] >= 1

    def test_process_single_role_collection_mode_saves(self, sample_single_role):
        generator = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        generator.process_single_role(str(sample_single_role), "sample_role")
        specs_file = sample_single_role / "meta" / "argument_specs.yml"
        assert specs_file.exists()


class TestLoadExistingSpecs:
    """Test load_existing_specs method."""

    def test_load_existing_specs_preserves_descriptions(self, sample_single_role):
        specs = {
            "argument_specs": {
                "main": {
                    "short_description": "My custom description",
                    "description": ["Line 1", "Line 2"],
                    "author": ["Me <me@example.com>"],
                    "options": {
                        "sample_role_port": {
                            "type": "int",
                            "description": "Custom port description",
                            "version_added": "0.5.0",
                        }
                    },
                }
            }
        }
        specs_file = sample_single_role / "meta" / "argument_specs.yml"
        specs_file.write_text(yaml.dump(specs))

        generator = ArgumentSpecsGenerator(verbosity=0)
        existing = generator.load_existing_specs(str(sample_single_role))

        assert "main" in existing
        assert existing["main"]["short_description"] == "My custom description"
        assert existing["main"]["description"] == ["Line 1", "Line 2"]
        assert existing["main"]["author"] == ["Me <me@example.com>"]
        assert (
            existing["main"]["options"]["sample_role_port"]["description"]
            == "Custom port description"
        )
        assert (
            existing["main"]["options"]["sample_role_port"]["version_added"] == "0.5.0"
        )
        assert existing["main"]["options"]["sample_role_port"]["_existing"] is True

    def test_load_existing_specs_no_file(self, temp_dir):
        generator = ArgumentSpecsGenerator()
        result = generator.load_existing_specs(str(temp_dir))
        assert result == {}

    def test_load_existing_specs_empty_file(self, sample_single_role):
        specs_file = sample_single_role / "meta" / "argument_specs.yml"
        specs_file.write_text("")
        generator = ArgumentSpecsGenerator()
        result = generator.load_existing_specs(str(sample_single_role))
        assert result == {}

    def test_load_existing_specs_invalid_yaml(self, sample_single_role):
        specs_file = sample_single_role / "meta" / "argument_specs.yml"
        specs_file.write_text("bad: yaml: {[")
        generator = ArgumentSpecsGenerator(verbosity=2)
        result = generator.load_existing_specs(str(sample_single_role))
        assert result == {}

    def test_load_existing_specs_missing_argument_specs_key(self, sample_single_role):
        specs_file = sample_single_role / "meta" / "argument_specs.yml"
        specs_file.write_text(yaml.dump({"other_key": "value"}))
        generator = ArgumentSpecsGenerator()
        result = generator.load_existing_specs(str(sample_single_role))
        assert result == {}


class TestValidateSpecs:
    """Test validate_specs method."""

    def test_validate_specs_valid(self):
        generator = ArgumentSpecsGenerator()
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={
                "my_var": ArgumentSpec(name="my_var", type="str", description="desc")
            },
        )
        generator.add_entry_point(ep)
        assert generator.validate_specs() is True

    def test_validate_specs_invalid_type(self):
        generator = ArgumentSpecsGenerator()
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={
                "bad": ArgumentSpec(name="bad", type="invalid_type", description="d")
            },
        )
        generator.add_entry_point(ep)
        assert generator.validate_specs() is False

    def test_validate_specs_required_if_unknown_param(self):
        generator = ArgumentSpecsGenerator()
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={"state": ArgumentSpec(name="state", type="str", description="d")},
            required_if=[["state", "present", ["nonexistent_param"]]],
        )
        generator.add_entry_point(ep)
        assert generator.validate_specs() is False

    def test_validate_specs_mutually_exclusive_unknown(self):
        generator = ArgumentSpecsGenerator()
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={"real": ArgumentSpec(name="real", type="str", description="d")},
            mutually_exclusive=[["real", "fake"]],
        )
        generator.add_entry_point(ep)
        assert generator.validate_specs() is False

    def test_validate_specs_required_one_of_unknown(self):
        generator = ArgumentSpecsGenerator()
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={"opt1": ArgumentSpec(name="opt1", type="str", description="d")},
            required_one_of=[["opt1", "missing"]],
        )
        generator.add_entry_point(ep)
        assert generator.validate_specs() is False

    def test_validate_specs_required_together_unknown(self):
        generator = ArgumentSpecsGenerator()
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={"opt1": ArgumentSpec(name="opt1", type="str", description="d")},
            required_together=[["opt1", "missing"]],
        )
        generator.add_entry_point(ep)
        assert generator.validate_specs() is False

    def test_validate_specs_no_short_description(self, capsys):
        generator = ArgumentSpecsGenerator(verbosity=2)
        ep = EntryPointSpec(
            name="main",
            options={"v": ArgumentSpec(name="v", type="str", description="d")},
        )
        generator.add_entry_point(ep)
        result = generator.validate_specs()
        assert result is True
        captured = capsys.readouterr()
        assert "No short_description" in captured.out

    def test_validate_specs_list_without_elements(self, capsys):
        generator = ArgumentSpecsGenerator(verbosity=2)
        ep = EntryPointSpec(
            name="main",
            short_description="Test",
            options={
                "mylist": ArgumentSpec(name="mylist", type="list", description="d")
            },
        )
        generator.add_entry_point(ep)
        result = generator.validate_specs()
        assert result is True
        captured = capsys.readouterr()
        assert "No elements type" in captured.out


class TestFromDefaultsFile:
    """Test from_defaults_file method."""

    def test_from_defaults_happy_path(self, temp_dir):
        defaults = {"app_name": "test", "app_port": 8080, "enabled": True}
        f = temp_dir / "defaults.yml"
        f.write_text(yaml.dump(defaults))
        generator = ArgumentSpecsGenerator(verbosity=1)
        generator.from_defaults_file(str(f))
        assert "main" in generator.entry_points
        ep = generator.entry_points["main"]
        assert "app_name" in ep.options
        assert "app_port" in ep.options
        assert "enabled" in ep.options

    def test_from_defaults_custom_entry_name(self, temp_dir):
        f = temp_dir / "defaults.yml"
        f.write_text(yaml.dump({"var1": "value"}))
        generator = ArgumentSpecsGenerator()
        generator.from_defaults_file(str(f), entry_name="install")
        assert "install" in generator.entry_points

    def test_from_defaults_empty_file(self, temp_dir):
        f = temp_dir / "empty.yml"
        f.touch()
        generator = ArgumentSpecsGenerator(verbosity=2)
        generator.from_defaults_file(str(f))
        assert "main" in generator.entry_points
        assert len(generator.entry_points["main"].options) == 0

    def test_from_defaults_non_dict_content(self, temp_dir):
        f = temp_dir / "list.yml"
        f.write_text("- item1\n- item2\n")
        generator = ArgumentSpecsGenerator(verbosity=2)
        generator.from_defaults_file(str(f))
        assert len(generator.entry_points["main"].options) == 0


class TestFromConfigFile:
    """Test from_config_file method."""

    def test_from_config_yaml_happy_path(self, temp_dir):
        config = {
            "entry_points": {
                "main": {
                    "short_description": "Main EP",
                    "description": ["Line 1"],
                    "author": ["Author <a@b.com>"],
                    "arguments": {
                        "my_var": {
                            "type": "str",
                            "required": True,
                            "description": "A variable",
                        }
                    },
                    "required_if": [["state", "present", ["my_var"]]],
                    "mutually_exclusive": [["a", "b"]],
                }
            }
        }
        f = temp_dir / "config.yml"
        f.write_text(yaml.dump(config))
        generator = ArgumentSpecsGenerator(verbosity=1)
        generator.from_config_file(str(f))
        assert "main" in generator.entry_points
        ep = generator.entry_points["main"]
        assert ep.short_description == "Main EP"
        assert ep.options["my_var"].required is True
        assert ep.required_if == [["state", "present", ["my_var"]]]

    def test_from_config_json(self, temp_dir):
        config = {
            "entry_points": {
                "main": {
                    "short_description": "JSON EP",
                    "arguments": {
                        "port": {
                            "type": "int",
                            "default": 80,
                            "description": "Port",
                        }
                    },
                }
            }
        }
        f = temp_dir / "config.json"
        f.write_text(json.dumps(config))
        generator = ArgumentSpecsGenerator()
        generator.from_config_file(str(f))
        assert generator.entry_points["main"].options["port"].default == 80

    def test_from_config_invalid_entry_point_skipped(self, temp_dir, capsys):
        config = {
            "entry_points": {
                "bad": "not_a_dict",
                "good": {
                    "short_description": "OK",
                    "arguments": {"v": {"type": "str", "description": "d"}},
                },
            }
        }
        f = temp_dir / "config.yml"
        f.write_text(yaml.dump(config))
        generator = ArgumentSpecsGenerator(verbosity=2)
        generator.from_config_file(str(f))
        assert "good" in generator.entry_points
        assert "bad" not in generator.entry_points

    def test_from_config_invalid_argument_skipped(self, temp_dir, capsys):
        config = {
            "entry_points": {
                "main": {
                    "short_description": "EP",
                    "arguments": {
                        "bad_arg": "not_a_dict",
                        "good_arg": {"type": "str", "description": "OK"},
                    },
                }
            }
        }
        f = temp_dir / "config.yml"
        f.write_text(yaml.dump(config))
        generator = ArgumentSpecsGenerator(verbosity=2)
        generator.from_config_file(str(f))
        ep = generator.entry_points["main"]
        assert "good_arg" in ep.options
        assert "bad_arg" not in ep.options

    def test_from_config_with_version_added(self, temp_dir):
        config = {
            "entry_points": {
                "main": {
                    "short_description": "EP",
                    "arguments": {
                        "va": {
                            "type": "str",
                            "description": "d",
                            "version_added": "2.0.0",
                        }
                    },
                }
            }
        }
        f = temp_dir / "config.yml"
        f.write_text(yaml.dump(config))
        generator = ArgumentSpecsGenerator()
        generator.from_config_file(str(f))
        assert generator.entry_points["main"].options["va"].version_added == "2.0.0"
