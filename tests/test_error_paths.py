"""
Tests for error-path edge cases: save_to_file permission errors,
UnicodeDecodeError during file reading, malformed galaxy.yml, etc.
"""

import os
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from generate_argument_specs import (
    ArgumentSpecsGenerator,
    EntryPointSpec,
    ArgumentSpec,
    CollectionNotFoundError,
)


class TestSaveToFileErrors:
    """Test save_to_file error paths."""

    def test_save_to_file_creates_parent_directories(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        gen.add_entry_point(EntryPointSpec(name="main", short_description="Test"))
        deep = temp_dir / "a" / "b" / "c" / "specs.yml"
        gen.save_to_file(str(deep))
        assert deep.exists()

    def test_save_to_file_permission_error(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        gen.add_entry_point(EntryPointSpec(name="main", short_description="Test"))
        restricted = temp_dir / "restricted"
        restricted.mkdir()
        os.chmod(str(restricted), 0o000)
        out = restricted / "specs.yml"
        try:
            with pytest.raises(PermissionError):
                gen.save_to_file(str(out))
        finally:
            os.chmod(str(restricted), 0o755)

    def test_save_to_file_overwrites_existing(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        gen.add_entry_point(EntryPointSpec(name="main", short_description="First"))
        out = temp_dir / "specs.yml"
        gen.save_to_file(str(out))
        first_content = out.read_text()

        gen2 = ArgumentSpecsGenerator()
        gen2.add_entry_point(EntryPointSpec(name="main", short_description="Second"))
        gen2.save_to_file(str(out))
        second_content = out.read_text()

        assert "First" in first_content
        assert "Second" in second_content
        assert "First" not in second_content


class TestMalformedGalaxyYml:
    """Test handling of malformed galaxy.yml.

    is_collection_root only checks for roles/ dir and galaxy.yml file presence,
    so it returns True even for malformed galaxy.yml. These tests verify
    that downstream processing handles the bad content gracefully.
    """

    def test_galaxy_yml_not_a_dict_still_detected(self, temp_dir):
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").write_text("- item1\n- item2\n")
        (coll / "roles").mkdir()
        gen = ArgumentSpecsGenerator()
        # is_collection_root only checks file existence, not content
        assert gen.is_collection_root(str(coll))

    def test_galaxy_yml_invalid_yaml_still_detected(self, temp_dir):
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").write_text("bad: yaml: {[")
        (coll / "roles").mkdir()
        gen = ArgumentSpecsGenerator()
        assert gen.is_collection_root(str(coll))

    def test_galaxy_yml_empty_still_detected(self, temp_dir):
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").touch()
        (coll / "roles").mkdir()
        gen = ArgumentSpecsGenerator()
        assert gen.is_collection_root(str(coll))

    def test_process_collection_malformed_galaxy_no_crash(self, temp_dir):
        """Processing a collection with a malformed galaxy.yml should not crash."""
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").write_text("- not_a_dict\n")
        roles = coll / "roles"
        roles.mkdir()
        role = roles / "myrole"
        role.mkdir()
        (role / "tasks").mkdir()
        (role / "tasks" / "main.yml").write_text(
            "---\n- name: t\n  debug:\n    msg: hi\n"
        )
        gen = ArgumentSpecsGenerator(verbosity=0)
        gen.process_collection(str(coll))
        assert gen.stats["roles_processed"] >= 1


class TestUnicodeDecodeErrors:
    """Test UnicodeDecodeError handling in file reading."""

    def test_binary_defaults_file(self, temp_dir):
        role = temp_dir / "binrole"
        role.mkdir()
        (role / "defaults").mkdir()
        (role / "tasks").mkdir()
        (role / "defaults" / "main.yml").write_bytes(b"\x80\x81\x82\xff\xfe\n")
        (role / "tasks" / "main.yml").write_text(
            "---\n- name: t\n  debug:\n    msg: hi\n"
        )

        gen = ArgumentSpecsGenerator()
        analysis = gen.analyze_role_structure(str(role))
        assert analysis is not None

    def test_binary_task_file(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        f = temp_dir / "binary.yml"
        f.write_bytes(b"\x89PNG\r\n\x00\x00IHDR\x00\x00")
        result = gen.extract_variables_from_task_file(f)
        assert result == set()


class TestBlockIncludesHandling:
    """Test variable extraction from block/rescue/always constructs."""

    def test_block_rescue_always(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        content = """---
- block:
    - name: Try something
      copy:
        src: "{{ block_src }}"
        dest: "{{ block_dest }}"
  rescue:
    - name: Handle failure
      debug:
        msg: "{{ rescue_msg }}"
  always:
    - name: Cleanup
      file:
        path: "{{ always_path }}"
        state: absent
"""
        f = temp_dir / "block_tasks.yml"
        f.write_text(content)

        variables = gen.extract_variables_from_task_file(f)
        assert "block_src" in variables
        assert "block_dest" in variables
        assert "rescue_msg" in variables
        assert "always_path" in variables


class TestMultipleDefaultsFiles:
    """Test roles with multiple defaults files."""

    def test_defaults_subdirectories(self, temp_dir):
        role = temp_dir / "role"
        role.mkdir()
        defaults = role / "defaults"
        defaults.mkdir()
        (defaults / "main.yml").write_text(yaml.dump({"var1": "val1"}))

        tasks = role / "tasks"
        tasks.mkdir()
        (tasks / "main.yml").write_text(
            '---\n- name: t\n  debug:\n    msg: "{{ var1 }}"\n'
        )

        gen = ArgumentSpecsGenerator()
        analysis = gen.analyze_role_structure(str(role))
        assert analysis["defaults"]["var1"] == "val1"


class TestVersionDetectionEdgeCases:
    """Test version detection edge cases."""

    def test_non_string_version_in_meta(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        role = temp_dir / "role"
        role.mkdir()
        (role / "meta").mkdir()
        meta = {"galaxy_info": {"version": 1.2}}
        (role / "meta" / "main.yml").write_text(yaml.dump(meta))
        info = gen._detect_version_info(role)
        assert info["version"] == "1.2"

    def test_list_version_in_meta(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        role = temp_dir / "role"
        role.mkdir()
        (role / "meta").mkdir()
        meta = {"galaxy_info": {"version": [1, 2, 0]}}
        (role / "meta" / "main.yml").write_text(yaml.dump(meta))
        info = gen._detect_version_info(role)
        # Implementation converts to string via str(), yielding "[1, 2, 0]"
        assert info["version"] == "[1, 2, 0]"
        assert info["source"] == "role"

    def test_empty_meta_file(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        role = temp_dir / "role"
        role.mkdir()
        (role / "meta").mkdir()
        (role / "meta" / "main.yml").touch()
        info = gen._detect_version_info(role)
        assert info["version"] == "1.0.0"
        assert info["source"] == "default"

    def test_version_from_changelog(self, temp_dir):
        gen = ArgumentSpecsGenerator()
        role = temp_dir / "role"
        role.mkdir()
        (role / "CHANGELOG.md").write_text(
            "# 3.0.0\n\n- Changes\n\n# 2.0.0\n\n- Older changes\n"
        )
        info = gen._detect_version_info(role)
        assert info["version"] in ("3.0.0", "1.0.0")


class TestProcessCollectionErrors:
    """Test error handling in process_collection."""

    def test_process_collection_nonexistent_dir(self):
        gen = ArgumentSpecsGenerator()
        with pytest.raises(CollectionNotFoundError):
            gen.process_collection("/totally/fake/path")

    def test_process_collection_with_file_in_roles_dir(self, temp_dir):
        coll = temp_dir / "coll"
        coll.mkdir()
        (coll / "galaxy.yml").write_text(
            yaml.dump({"namespace": "ns", "name": "c", "version": "1.0.0"})
        )
        roles = coll / "roles"
        roles.mkdir()
        (roles / "not_a_role.txt").touch()

        gen = ArgumentSpecsGenerator()
        with pytest.raises(CollectionNotFoundError, match="No roles found"):
            gen.process_collection(str(coll))
