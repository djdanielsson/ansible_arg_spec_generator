"""
Tests for CLI flags: --dry-run, --quiet, --role, --collection-path, --from-config.
"""

import json
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from generate_argument_specs import main


class TestDryRun:
    """Test --dry-run flag."""

    def test_dry_run_collection_does_not_write(self, monkeypatch, sample_collection_structure):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--dry-run"]):
            main()

        for role_dir in (sample_collection_structure / "roles").iterdir():
            specs = role_dir / "meta" / "argument_specs.yml"
            assert not specs.exists(), f"Dry run should not create {specs}"

    def test_dry_run_single_role_prints_yaml(self, monkeypatch, sample_single_role, capsys):
        monkeypatch.chdir(sample_single_role)
        with patch(
            "sys.argv",
            ["prog", "--single-role", "--from-defaults", "defaults/main.yml", "--dry-run"],
        ):
            main()
        captured = capsys.readouterr()
        assert "argument_specs" in captured.out
        assert "Dry run" in captured.out
        output = sample_single_role / "meta" / "argument_specs.yml"
        assert not output.exists()

    def test_dry_run_save_to_file(self, temp_dir):
        from generate_argument_specs import ArgumentSpecsGenerator, EntryPointSpec

        gen = ArgumentSpecsGenerator(dry_run=True, verbosity=1)
        ep = EntryPointSpec(name="main", short_description="Test")
        gen.add_entry_point(ep)
        out = temp_dir / "specs.yml"
        gen.save_to_file(str(out))
        assert not out.exists()

    def test_dry_run_save_role_specs(self, sample_single_role):
        from generate_argument_specs import ArgumentSpecsGenerator, EntryPointSpec

        gen = ArgumentSpecsGenerator(dry_run=True, verbosity=2)
        ep = EntryPointSpec(name="main", short_description="Test")
        gen.add_entry_point(ep)
        gen.save_role_specs(str(sample_single_role), "sample_role")
        specs = sample_single_role / "meta" / "argument_specs.yml"
        assert not specs.exists()


class TestQuiet:
    """Test --quiet / -q flag."""

    def test_quiet_suppresses_processing_output(self, monkeypatch, sample_collection_structure, capsys):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--quiet"]):
            main()
        captured = capsys.readouterr()
        assert "Processing role" not in captured.out

    def test_quiet_with_verbose_no_verbose_output(self, monkeypatch, sample_collection_structure, capsys):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--quiet"]):
            main()
        captured = capsys.readouterr()
        assert "Analyzing" not in captured.out


class TestCollectionPathFlag:
    """Test --collection-path flag."""

    def test_collection_path_flag(self, monkeypatch, sample_collection_structure, temp_dir):
        monkeypatch.chdir(temp_dir)
        with patch(
            "sys.argv",
            ["prog", "--collection-path", str(sample_collection_structure)],
        ):
            main()
        for role_dir in (sample_collection_structure / "roles").iterdir():
            specs = role_dir / "meta" / "argument_specs.yml"
            assert specs.exists()


class TestRoleFlag:
    """Test --role flag to process a single role within a collection."""

    def test_role_flag_processes_single_role(self, monkeypatch, sample_collection_structure, capsys):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--role", "webapp"]):
            main()
        specs = (
            sample_collection_structure
            / "roles"
            / "webapp"
            / "meta"
            / "argument_specs.yml"
        )
        assert specs.exists()
        captured = capsys.readouterr()
        assert "1 role" in captured.out


class TestFromConfigFlag:
    """Test --from-config flag."""

    def test_from_config_flag(self, monkeypatch, temp_dir, capsys):
        config = {
            "entry_points": {
                "main": {
                    "short_description": "Test EP",
                    "arguments": {
                        "my_var": {
                            "type": "str",
                            "required": True,
                            "description": "A variable",
                        }
                    },
                }
            }
        }
        config_file = temp_dir / "config.yml"
        config_file.write_text(yaml.dump(config))
        output = temp_dir / "out.yml"
        monkeypatch.chdir(temp_dir)
        with patch(
            "sys.argv",
            [
                "prog",
                "--single-role",
                "--from-config",
                str(config_file),
                "-o",
                str(output),
            ],
        ):
            main()
        assert output.exists()
        content = yaml.safe_load(output.read_text())
        assert "argument_specs" in content
        assert "my_var" in content["argument_specs"]["main"]["options"]


class TestMutuallyExclusiveArgs:
    """Test mutually exclusive argument combinations."""

    def test_from_defaults_in_collection_mode(self, monkeypatch, sample_collection_structure, capsys):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--from-defaults", "defaults/main.yml"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_from_config_in_collection_mode(self, monkeypatch, sample_collection_structure, capsys):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--from-config", "config.yml"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_list_roles_in_single_role_mode(self, monkeypatch, temp_dir):
        monkeypatch.chdir(temp_dir)
        with patch("sys.argv", ["prog", "--single-role", "--list-roles"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_role_flag_in_single_role_mode(self, monkeypatch, temp_dir):
        monkeypatch.chdir(temp_dir)
        with patch("sys.argv", ["prog", "--single-role", "--role", "foo"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
