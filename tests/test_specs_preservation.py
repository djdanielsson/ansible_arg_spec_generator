"""
Tests for preserving existing specs during regeneration:
descriptions, author, version_added are kept intact.
"""

import pytest
import yaml
from pathlib import Path

from generate_argument_specs import ArgumentSpecsGenerator


class TestExistingSpecsPreservation:
    """Test that regeneration preserves manually written descriptions and metadata."""

    def _make_role_with_existing_specs(self, temp_dir, existing_specs):
        """Helper: create a role with defaults and pre-existing argument_specs.yml."""
        role = temp_dir / "myrole"
        role.mkdir()
        (role / "defaults").mkdir()
        (role / "tasks").mkdir()
        (role / "meta").mkdir()

        defaults = {
            "myrole_port": 8080,
            "myrole_enabled": True,
            "myrole_name": "myapp",
        }
        (role / "defaults" / "main.yml").write_text(yaml.dump(defaults))
        (role / "tasks" / "main.yml").write_text(
            "---\n- name: Use vars\n  debug:\n    msg: \"{{ myrole_port }}\"\n"
        )

        meta = {"galaxy_info": {"author": "Role Author", "description": "Role desc"}}
        (role / "meta" / "main.yml").write_text(yaml.dump(meta))

        (role / "meta" / "argument_specs.yml").write_text(yaml.dump(existing_specs))
        return role

    def test_description_preserved(self, temp_dir):
        existing = {
            "argument_specs": {
                "main": {
                    "short_description": "My custom short desc",
                    "description": ["My custom long description"],
                    "author": ["Custom Author <custom@example.com>"],
                    "options": {
                        "myrole_port": {
                            "type": "int",
                            "description": "Custom port description",
                            "version_added": "0.1.0",
                        },
                        "myrole_enabled": {
                            "type": "bool",
                            "description": "Custom enable description",
                        },
                    },
                }
            }
        }
        role = self._make_role_with_existing_specs(temp_dir, existing)

        gen = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        gen.process_single_role(str(role), "myrole")

        ep = gen.entry_points["main"]
        assert ep.short_description == "My custom short desc"
        assert ep.description == ["My custom long description"]
        assert ep.author == ["Custom Author <custom@example.com>"]

        assert ep.options["myrole_port"].description == "Custom port description"
        assert ep.options["myrole_port"].version_added == "0.1.0"
        assert ep.options["myrole_enabled"].description == "Custom enable description"

    def test_version_added_not_set_for_existing_vars(self, temp_dir):
        existing = {
            "argument_specs": {
                "main": {
                    "short_description": "Test",
                    "options": {
                        "myrole_port": {
                            "type": "int",
                            "description": "Port",
                        },
                    },
                }
            }
        }
        role = self._make_role_with_existing_specs(temp_dir, existing)
        gen = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        gen.process_single_role(str(role), "myrole")

        ep = gen.entry_points["main"]
        assert ep.options["myrole_port"].version_added is None

    def test_new_variable_gets_version_added(self, temp_dir):
        existing = {
            "argument_specs": {
                "main": {
                    "short_description": "Test",
                    "options": {},
                }
            }
        }
        role = self._make_role_with_existing_specs(temp_dir, existing)
        gen = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)
        gen.process_single_role(str(role), "myrole")

        ep = gen.entry_points["main"]
        assert ep.options["myrole_port"].version_added is not None

    def test_regeneration_roundtrip(self, temp_dir):
        """Generate specs, then regenerate and verify nothing changed."""
        role = temp_dir / "roundtrip"
        role.mkdir()
        (role / "defaults").mkdir()
        (role / "tasks").mkdir()
        (role / "meta").mkdir()

        defaults = {"rt_port": 9090, "rt_name": "roundtrip"}
        (role / "defaults" / "main.yml").write_text(yaml.dump(defaults))
        (role / "tasks" / "main.yml").write_text(
            "---\n- name: t\n  debug:\n    msg: \"{{ rt_port }}\"\n"
        )
        meta = {"galaxy_info": {"author": "RT Author"}}
        (role / "meta" / "main.yml").write_text(yaml.dump(meta))

        gen1 = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        gen1.process_single_role(str(role), "roundtrip")
        first_yaml = (role / "meta" / "argument_specs.yml").read_text()

        gen2 = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)
        gen2.process_single_role(str(role), "roundtrip")
        second_yaml = (role / "meta" / "argument_specs.yml").read_text()

        first = yaml.safe_load(first_yaml)
        second = yaml.safe_load(second_yaml)
        assert first == second
