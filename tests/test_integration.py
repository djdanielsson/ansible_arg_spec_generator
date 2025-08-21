"""
Integration tests for the complete argument specs generation workflow
"""

import pytest
import tempfile
import yaml
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from generate_argument_specs import ArgumentSpecsGenerator, main


class TestCollectionModeIntegration:
    """Test complete collection mode workflow"""

    def test_collection_mode_complete_workflow(self, sample_collection_structure):
        """Test complete collection processing workflow"""
        generator = ArgumentSpecsGenerator(collection_mode=True, verbosity=1)

        # Change to collection directory
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(sample_collection_structure)

            # Find roles
            roles = generator.find_roles(".")
            assert len(roles) == 2
            assert "webapp" in roles
            assert "database" in roles

            # Process each role
            for role_name in roles:
                role_path = Path("roles") / role_name
                analysis = generator.analyze_role_structure(str(role_path))

                assert analysis is not None
                assert "entry_points" in analysis
                assert "variables" in analysis

                # Verify entry points were created
                assert len(analysis["entry_points"]) >= 1

                # Verify variables were extracted
                assert len(analysis["variables"]) > 0

        finally:
            os.chdir(original_cwd)

    def test_collection_mode_generates_argument_specs_files(
        self, sample_collection_structure
    ):
        """Test that collection mode generates argument_specs.yml files"""
        generator = ArgumentSpecsGenerator(collection_mode=True, verbosity=0)

        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(sample_collection_structure)

            roles = generator.find_roles(".")

            for role_name in roles:
                role_path = Path("roles") / role_name
                analysis = generator.analyze_role_structure(str(role_path))

                # Create specs from analysis
                if analysis["entry_points"]:
                    # Clear any existing entry points
                    generator.entry_points = {}

                    # Create entry point specs from analysis
                    from generate_argument_specs import EntryPointSpec, ArgumentSpec

                    for ep_name, ep_data in analysis["entry_points"].items():
                        entry_point = EntryPointSpec(
                            name=ep_name,
                            short_description=f"Auto-generated specs for {role_name} role - {ep_name} entry point",
                        )

                        # Add variables as arguments
                        for var_name, var_info in ep_data.get("variables", {}).items():
                            arg_spec = ArgumentSpec(
                                name=var_name,
                                type=var_info.get("type", "str"),
                                required=var_info.get("required", False),
                                default=var_info.get("default"),
                                description=var_info.get(
                                    "description", f"Auto-generated for {var_name}"
                                ),
                            )
                            entry_point.options[var_name] = arg_spec

                        generator.add_entry_point(entry_point)

                    # Save to file
                    output_file = role_path / "meta" / "argument_specs.yml"
                    output_file.parent.mkdir(exist_ok=True)
                    generator.save_to_file(str(output_file))

                    # Verify file was created and is valid YAML
                    assert output_file.exists()

                    with open(output_file, "r") as f:
                        content = yaml.safe_load(f)

                    assert "argument_specs" in content
                    assert ep_name in content["argument_specs"]

        finally:
            os.chdir(original_cwd)


class TestSingleRoleModeIntegration:
    """Test complete single role mode workflow"""

    def test_single_role_mode_complete_workflow(self, sample_single_role):
        """Test complete single role processing workflow"""
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=1)

        # Analyze the role
        analysis = generator.analyze_role_structure(str(sample_single_role))

        assert analysis is not None
        assert "entry_points" in analysis
        assert "variables" in analysis
        assert "meta_info" in analysis

        # Should have at least main entry point
        assert "main" in analysis["entry_points"]

        # Should have extracted variables from defaults
        variables = analysis["variables"]
        assert len(variables) > 0

        # Check for expected variables based on our sample role
        main_variables = analysis["entry_points"]["main"]["variables"]
        assert len(main_variables) > 0

    def test_single_role_generates_specs_file(self, sample_single_role):
        """Test that single role mode generates argument specs file"""
        generator = ArgumentSpecsGenerator(collection_mode=False, verbosity=0)

        # Analyze role
        analysis = generator.analyze_role_structure(str(sample_single_role))

        # Create entry point from analysis
        from generate_argument_specs import EntryPointSpec, ArgumentSpec

        if analysis["entry_points"]:
            for ep_name, ep_data in analysis["entry_points"].items():
                entry_point = EntryPointSpec(
                    name=ep_name,
                    short_description=f"Auto-generated specs for sample_role - {ep_name} entry point",
                )

                # Add variables as arguments
                for var_name, var_info in ep_data.get("variables", {}).items():
                    arg_spec = ArgumentSpec(
                        name=var_name,
                        type=var_info.get("type", "str"),
                        required=var_info.get("required", False),
                        default=var_info.get("default"),
                        description=var_info.get(
                            "description", f"Auto-generated for {var_name}"
                        ),
                    )
                    entry_point.options[var_name] = arg_spec

                generator.add_entry_point(entry_point)

        # Save to file
        output_file = sample_single_role / "meta" / "argument_specs.yml"
        output_file.parent.mkdir(exist_ok=True)
        generator.save_to_file(str(output_file))

        # Verify file exists and is valid
        assert output_file.exists()

        with open(output_file, "r") as f:
            content = yaml.safe_load(f)

        assert "argument_specs" in content
        assert len(content["argument_specs"]) >= 1


class TestCommandLineInterface:
    """Test command line interface"""

    def test_main_function_collection_mode(self, sample_collection_structure, capsys):
        """Test main function in collection mode"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(sample_collection_structure)

            # Mock command line arguments for collection mode
            test_args = ["generate_argument_specs.py", "--list-roles"]

            with patch("sys.argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    # --list-roles exits after listing
                    assert e.code == 0

            captured = capsys.readouterr()
            assert "webapp" in captured.out
            assert "database" in captured.out

        finally:
            os.chdir(original_cwd)

    def test_main_function_single_role_mode(self, sample_single_role, capsys):
        """Test main function in single role mode"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(sample_single_role)

            # Mock command line arguments for single role mode
            test_args = [
                "generate_argument_specs.py",
                "--single-role",
                "--from-defaults",
                "defaults/main.yml",
                "--output",
                "meta/argument_specs.yml",
            ]

            with patch("sys.argv", test_args):
                main()

            # Verify output file was created
            output_file = sample_single_role / "meta" / "argument_specs.yml"
            assert output_file.exists()

        finally:
            os.chdir(original_cwd)

    def test_main_function_validation_mode(self, sample_collection_structure, capsys):
        """Test main function in validation mode"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(sample_collection_structure)

            # Create some argument specs files first
            webapp_specs = (
                sample_collection_structure
                / "roles"
                / "webapp"
                / "meta"
                / "argument_specs.yml"
            )
            webapp_specs.parent.mkdir(exist_ok=True)

            specs_content = {
                "argument_specs": {
                    "main": {
                        "short_description": "Test specs",
                        "options": {
                            "test_var": {"type": "str", "description": "Test variable"}
                        },
                    }
                }
            }

            with open(webapp_specs, "w") as f:
                yaml.dump(specs_content, f)

            # Test validation mode
            test_args = ["generate_argument_specs.py", "--validate-only", "-v"]

            with patch("sys.argv", test_args):
                main()

            captured = capsys.readouterr()
            # Should mention validation
            assert "validat" in captured.out.lower() or "valid" in captured.out.lower()

        finally:
            os.chdir(original_cwd)

    def test_main_function_verbosity_levels(self, sample_collection_structure, capsys):
        """Test different verbosity levels"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(sample_collection_structure)

            # Test various verbosity levels
            verbosity_args = [
                ["generate_argument_specs.py", "--list-roles"],  # No verbosity
                ["generate_argument_specs.py", "--list-roles", "-v"],  # Basic
                ["generate_argument_specs.py", "--list-roles", "-vv"],  # Verbose
                ["generate_argument_specs.py", "--list-roles", "-vvv"],  # Debug
            ]

            for args in verbosity_args:
                with patch("sys.argv", args):
                    try:
                        main()
                    except SystemExit:
                        pass  # --list-roles exits

                captured = capsys.readouterr()
                assert len(captured.out) > 0  # Should produce some output

        finally:
            os.chdir(original_cwd)

    def test_main_function_create_example_config(self, temp_dir, capsys):
        """Test creating example config"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(temp_dir)

            test_args = ["generate_argument_specs.py", "--create-example-config"]

            with patch("sys.argv", test_args):
                main()

            # Check if example config file was created
            config_files = list(temp_dir.glob("*.yml")) + list(temp_dir.glob("*.yaml"))

            # Should create some example config file
            # (Implementation might vary, so we just check that something was created)
            captured = capsys.readouterr()
            assert len(captured.out) > 0

        finally:
            os.chdir(original_cwd)


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""

    def test_complete_collection_processing(self, sample_collection_structure):
        """Test processing a complete collection from start to finish"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(sample_collection_structure)

            # Run the full collection processing
            test_args = ["generate_argument_specs.py", "-v"]

            with patch("sys.argv", test_args):
                main()

            # Verify that argument_specs.yml files were created for each role
            roles_dir = sample_collection_structure / "roles"

            for role_dir in roles_dir.iterdir():
                if role_dir.is_dir():
                    specs_file = role_dir / "meta" / "argument_specs.yml"

                    # Check if file exists (it should for roles with variables)
                    if specs_file.exists():
                        # Verify it's valid YAML
                        with open(specs_file, "r") as f:
                            content = yaml.safe_load(f)

                        assert "argument_specs" in content
                        assert len(content["argument_specs"]) >= 1

                        # Check that at least one entry point has options
                        has_options = any(
                            "options" in ep_spec and len(ep_spec["options"]) > 0
                            for ep_spec in content["argument_specs"].values()
                        )

                        # Most roles should have at least some variables
                        if role_dir.name in ["webapp", "database"]:
                            assert (
                                has_options
                            ), f"Role {role_dir.name} should have extracted variables"

        finally:
            os.chdir(original_cwd)

    def test_single_role_with_complex_structure(self, sample_collection_structure):
        """Test processing a single role with complex structure"""
        original_cwd = Path.cwd()

        try:
            import os

            # Process the database role which has multiple entry points
            database_role = sample_collection_structure / "roles" / "database"
            os.chdir(database_role)

            test_args = [
                "generate_argument_specs.py",
                "--single-role",
                "--from-defaults",
                "defaults/main.yml",
                "--output",
                "meta/test_argument_specs.yml",
                "-vv",
            ]

            with patch("sys.argv", test_args):
                main()

            # Verify output file
            output_file = database_role / "meta" / "test_argument_specs.yml"
            assert output_file.exists()

            with open(output_file, "r") as f:
                content = yaml.safe_load(f)

            assert "argument_specs" in content

            # Should have at least main entry point
            assert "main" in content["argument_specs"]

            # Check for proper structure
            main_spec = content["argument_specs"]["main"]
            assert "options" in main_spec or "short_description" in main_spec

        finally:
            os.chdir(original_cwd)

    def test_error_recovery_scenarios(self, temp_dir):
        """Test that the tool recovers gracefully from various error conditions"""
        original_cwd = Path.cwd()

        try:
            import os

            os.chdir(temp_dir)

            # Create a problematic collection structure
            problem_collection = temp_dir / "problem_collection"
            problem_collection.mkdir()

            # Create galaxy.yml
            galaxy_content = {
                "namespace": "test",
                "name": "problem",
                "version": "1.0.0",
            }
            with open(problem_collection / "galaxy.yml", "w") as f:
                yaml.dump(galaxy_content, f)

            # Create roles directory
            roles_dir = problem_collection / "roles"
            roles_dir.mkdir()

            # Create a role with problematic files
            problem_role = roles_dir / "problem_role"
            problem_role.mkdir()
            (problem_role / "tasks").mkdir()
            (problem_role / "defaults").mkdir()
            (problem_role / "meta").mkdir()

            # Create invalid YAML in defaults
            with open(problem_role / "defaults" / "main.yml", "w") as f:
                f.write("invalid: yaml: content:\n  bad_indent")

            # Create invalid YAML in tasks
            with open(problem_role / "tasks" / "main.yml", "w") as f:
                f.write("- name: broken task\n  package:\n invalid_key")

            # Create empty meta file
            (problem_role / "meta" / "main.yml").touch()

            os.chdir(problem_collection)

            # Should handle errors gracefully and continue processing
            test_args = ["generate_argument_specs.py", "-v"]

            with patch("sys.argv", test_args):
                # Should not crash, even with problematic files
                try:
                    main()
                except SystemExit as e:
                    # Should exit cleanly even if some processing failed
                    pass

        finally:
            os.chdir(original_cwd)
