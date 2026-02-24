"""
Tests for exception raise paths across the generator.
"""

import json
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from generate_argument_specs import (
    ArgumentSpecsGenerator,
    ArgumentSpec,
    EntryPointSpec,
    GeneratorError,
    CollectionNotFoundError,
    RoleNotFoundError,
    ConfigError,
    ValidationError,
    main,
)


class TestCollectionNotFoundError:
    """Test that CollectionNotFoundError is raised correctly."""

    def test_process_collection_not_a_collection(self, temp_dir):
        generator = ArgumentSpecsGenerator()
        with pytest.raises(CollectionNotFoundError, match="does not appear"):
            generator.process_collection(str(temp_dir))

    def test_process_collection_no_roles(self, temp_dir):
        (temp_dir / "roles").mkdir()
        (temp_dir / "galaxy.yml").write_text(
            yaml.dump({"namespace": "ns", "name": "c", "version": "1.0.0"})
        )
        generator = ArgumentSpecsGenerator()
        with pytest.raises(CollectionNotFoundError, match="No roles found"):
            generator.process_collection(str(temp_dir))

    def test_main_list_roles_not_collection(self, monkeypatch, temp_dir):
        monkeypatch.chdir(temp_dir)
        with patch("sys.argv", ["prog", "--list-roles"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestRoleNotFoundError:
    """Test that RoleNotFoundError is raised correctly."""

    def test_main_role_not_found(self, monkeypatch, sample_collection_structure):
        monkeypatch.chdir(sample_collection_structure)
        with patch("sys.argv", ["prog", "--role", "nonexistent_role"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestConfigError:
    """Test that ConfigError is raised correctly."""

    def test_from_defaults_file_missing(self):
        generator = ArgumentSpecsGenerator()
        with pytest.raises(ConfigError, match="not found"):
            generator.from_defaults_file("/does/not/exist.yml")

    def test_from_config_file_missing(self):
        generator = ArgumentSpecsGenerator()
        with pytest.raises(ConfigError, match="not found"):
            generator.from_config_file("/does/not/exist.yml")

    def test_from_config_file_empty(self, temp_dir):
        empty = temp_dir / "empty.yml"
        empty.touch()
        generator = ArgumentSpecsGenerator()
        with pytest.raises(ConfigError, match="empty"):
            generator.from_config_file(str(empty))

    def test_from_config_file_not_dict(self, temp_dir):
        f = temp_dir / "list.yml"
        f.write_text("- item1\n- item2\n")
        generator = ArgumentSpecsGenerator()
        with pytest.raises(ConfigError, match="must contain a dictionary"):
            generator.from_config_file(str(f))

    def test_from_config_file_no_entry_points(self, temp_dir):
        f = temp_dir / "no_ep.yml"
        f.write_text(yaml.dump({"some_key": "some_value"}))
        generator = ArgumentSpecsGenerator()
        with pytest.raises(ConfigError, match="entry_points"):
            generator.from_config_file(str(f))

    def test_main_validate_only_missing_file(self, monkeypatch, temp_dir):
        monkeypatch.chdir(temp_dir)
        with patch(
            "sys.argv",
            ["prog", "--single-role", "--validate-only", "-o", "missing.yml"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestValidationError:
    """Test that ValidationError is raised correctly."""

    def test_main_single_role_validation_failure(self, monkeypatch, temp_dir):
        monkeypatch.chdir(temp_dir)
        specs = {
            "argument_specs": {
                "main": {
                    "short_description": "Test",
                    "options": {
                        "bad_var": {"type": "invalid_type", "description": "bad"}
                    },
                }
            }
        }
        specs_file = temp_dir / "meta" / "argument_specs.yml"
        specs_file.parent.mkdir(parents=True)
        specs_file.write_text(yaml.dump(specs))
        with patch(
            "sys.argv",
            ["prog", "--single-role", "--validate-only", "-o", str(specs_file)],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_validate_collection_failure(self, monkeypatch, temp_dir):
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").write_text(
            yaml.dump({"namespace": "ns", "name": "c", "version": "1.0.0"})
        )
        roles = coll / "roles"
        roles.mkdir()
        role = roles / "bad_role"
        role.mkdir()
        (role / "tasks").mkdir()
        (role / "tasks" / "main.yml").write_text(
            "---\n- name: t\n  debug:\n    msg: hi\n"
        )
        meta = role / "meta"
        meta.mkdir()
        specs = {
            "argument_specs": {
                "main": {
                    "short_description": "Test",
                    "options": {
                        "bad_var": {"type": "NOT_A_TYPE", "description": "bad"}
                    },
                }
            }
        }
        (meta / "argument_specs.yml").write_text(yaml.dump(specs))
        monkeypatch.chdir(coll)
        with patch("sys.argv", ["prog", "--validate-only"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestExceptionHierarchy:
    """Test that exception classes inherit correctly."""

    def test_all_inherit_from_generator_error(self):
        assert issubclass(CollectionNotFoundError, GeneratorError)
        assert issubclass(RoleNotFoundError, GeneratorError)
        assert issubclass(ConfigError, GeneratorError)
        assert issubclass(ValidationError, GeneratorError)

    def test_generator_error_inherits_from_exception(self):
        assert issubclass(GeneratorError, Exception)

    def test_main_catches_generator_error(self, monkeypatch, temp_dir):
        monkeypatch.chdir(temp_dir)
        with patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
