#!/usr/bin/env python3
"""
Test completeness checker for ansible-argument-spec-generator

This script verifies that all code modules have corresponding tests
and checks for potential gaps in test coverage.
"""

import ast
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple


def get_classes_and_functions(file_path: Path) -> Tuple[Set[str], Set[str]]:
    """Extract class and function names from a Python file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        classes = set()
        functions = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name)
            elif isinstance(node, ast.FunctionDef):
                # Skip private methods and special methods
                if not node.name.startswith("_"):
                    functions.add(node.name)

        return classes, functions

    except Exception as e:
        print(f"⚠️  Warning: Could not parse {file_path}: {e}")
        return set(), set()


def get_test_coverage(test_dir: Path) -> Dict[str, Set[str]]:
    """Get all test functions organized by test file"""
    test_coverage = {}

    for test_file in test_dir.glob("test_*.py"):
        try:
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            test_functions = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    test_functions.add(node.name)

            test_coverage[test_file.name] = test_functions

        except Exception as e:
            print(f"⚠️  Warning: Could not parse test file {test_file}: {e}")

    return test_coverage


def check_main_module_coverage() -> bool:
    """Check that the main module has adequate test coverage"""
    print("🔍 Checking main module test coverage...")

    main_pkg = Path("generate_argument_specs")
    if not main_pkg.exists():
        print("❌ ERROR: Main package generate_argument_specs/ not found")
        return False

    # Extract classes and functions from all package modules
    classes: set = set()
    functions: set = set()
    for py_file in main_pkg.glob("*.py"):
        file_classes, file_functions = get_classes_and_functions(py_file)
        classes.update(file_classes)
        functions.update(file_functions)

    print(f"📊 Found in main module:")
    print(f"   Classes: {len(classes)} - {', '.join(sorted(classes))}")
    print(f"   Functions: {len(functions)} - {', '.join(sorted(functions))}")

    # Check that major classes have dedicated test files
    major_classes = {"ArgumentSpec", "EntryPointSpec", "ArgumentSpecsGenerator"}

    for cls in major_classes:
        if cls not in classes:
            print(f"⚠️  Warning: Expected class {cls} not found in main module")

    # Verify test files exist for major components
    test_dir = Path("tests")
    if not test_dir.exists():
        print("❌ ERROR: Tests directory not found")
        return False

    required_test_files = {
        "test_basic.py": "Basic smoke tests",
        "test_argument_spec.py": "ArgumentSpec and EntryPointSpec classes",
        "test_generator_core.py": "ArgumentSpecsGenerator core functionality",
        "test_variable_extraction.py": "Variable extraction and parsing",
        "test_integration.py": "Integration and end-to-end tests",
        "test_edge_cases.py": "Edge cases and error handling",
        "test_type_inference.py": "Type inference and smart descriptions",
    }

    missing_files = []
    for test_file, description in required_test_files.items():
        test_path = test_dir / test_file
        if not test_path.exists():
            missing_files.append(f"{test_file} ({description})")
        else:
            print(f"✅ Found: {test_file}")

    if missing_files:
        print("❌ ERROR: Missing required test files:")
        for missing in missing_files:
            print(f"   - {missing}")
        return False

    return True


def check_test_function_coverage() -> bool:
    """Check that we have adequate test function coverage"""
    print("\n🔍 Checking test function coverage...")

    test_dir = Path("tests")
    test_coverage = get_test_coverage(test_dir)

    total_tests = 0
    for test_file, test_functions in test_coverage.items():
        test_count = len(test_functions)
        total_tests += test_count
        print(f"📋 {test_file}: {test_count} tests")

        # Check for minimum test count in each file
        if test_count < 3:
            print(
                f"⚠️  Warning: {test_file} has only {test_count} tests (expected at least 3)"
            )

    print(f"\n📊 Total test functions: {total_tests}")

    # Check minimum total test count
    MIN_TOTAL_TESTS = 50
    if total_tests < MIN_TOTAL_TESTS:
        print(
            f"❌ ERROR: Only {total_tests} test functions found (expected at least {MIN_TOTAL_TESTS})"
        )
        return False

    print(f"✅ Good test coverage: {total_tests} test functions")
    return True


def check_test_naming_conventions() -> bool:
    """Check that test files follow naming conventions"""
    print("\n🔍 Checking test naming conventions...")

    test_dir = Path("tests")
    issues_found = []

    # Check test files
    for py_file in test_dir.glob("*.py"):
        if py_file.name in ["__init__.py", "conftest.py"]:
            continue

        if not py_file.name.startswith("test_"):
            issues_found.append(
                f"File {py_file.name} doesn't follow 'test_*.py' convention"
            )

    # Check test functions in test files
    test_coverage = get_test_coverage(test_dir)
    for test_file, test_functions in test_coverage.items():
        for func in test_functions:
            if not func.startswith("test_"):
                issues_found.append(
                    f"Function {func} in {test_file} doesn't start with 'test_'"
                )

    if issues_found:
        print("❌ ERROR: Naming convention issues found:")
        for issue in issues_found:
            print(f"   - {issue}")
        return False

    print("✅ All test files and functions follow naming conventions")
    return True


def check_test_categories_coverage() -> bool:
    """Check that all important functionality categories are tested"""
    print("\n🔍 Checking test category coverage...")

    test_dir = Path("tests")

    # Define expected test categories and what they should cover
    expected_categories = {
        "basic": {
            "file": "test_basic.py",
            "required_patterns": ["import", "initialization", "yaml"],
            "description": "Basic smoke tests",
        },
        "argument_spec": {
            "file": "test_argument_spec.py",
            "required_patterns": ["ArgumentSpec", "EntryPointSpec", "to_dict"],
            "description": "Core dataclass functionality",
        },
        "generator_core": {
            "file": "test_generator_core.py",
            "required_patterns": ["generator", "logging", "collection", "yaml"],
            "description": "Main generator functionality",
        },
        "variable_extraction": {
            "file": "test_variable_extraction.py",
            "required_patterns": ["extract", "variable", "task", "jinja"],
            "description": "Variable detection and extraction",
        },
        "integration": {
            "file": "test_integration.py",
            "required_patterns": ["integration", "workflow", "end", "cli"],
            "description": "End-to-end testing",
        },
        "edge_cases": {
            "file": "test_edge_cases.py",
            "required_patterns": ["edge", "error", "invalid", "malformed"],
            "description": "Error handling and edge cases",
        },
        "type_inference": {
            "file": "test_type_inference.py",
            "required_patterns": ["type", "inference", "smart", "description"],
            "description": "Type detection and smart features",
        },
    }

    missing_categories = []
    incomplete_categories = []

    for category, info in expected_categories.items():
        test_file_path = test_dir / info["file"]

        if not test_file_path.exists():
            missing_categories.append(f"{info['file']} ({info['description']})")
            continue

        # Check if test file contains expected patterns
        try:
            with open(test_file_path, "r", encoding="utf-8") as f:
                content = f.read().lower()

            missing_patterns = []
            for pattern in info["required_patterns"]:
                if pattern.lower() not in content:
                    missing_patterns.append(pattern)

            if missing_patterns:
                incomplete_categories.append(
                    f"{info['file']} missing patterns: {', '.join(missing_patterns)}"
                )
            else:
                print(f"✅ {category}: {info['file']} - {info['description']}")

        except Exception as e:
            incomplete_categories.append(f"{info['file']} could not be analyzed: {e}")

    success = True

    if missing_categories:
        print("❌ ERROR: Missing test categories:")
        for missing in missing_categories:
            print(f"   - {missing}")
        success = False

    if incomplete_categories:
        print("⚠️  Warning: Incomplete test categories:")
        for incomplete in incomplete_categories:
            print(f"   - {incomplete}")
        # Don't fail for incomplete patterns, just warn

    return success


def check_fixture_completeness() -> bool:
    """Check that conftest.py has adequate fixtures"""
    print("\n🔍 Checking test fixtures...")

    conftest_path = Path("tests/conftest.py")
    if not conftest_path.exists():
        print("❌ ERROR: conftest.py not found in tests directory")
        return False

    try:
        with open(conftest_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for expected fixtures
        expected_fixtures = [
            "temp_dir",
            "sample_collection_structure",
            "sample_single_role",
            "generator",
            "sample_argument_spec",
            "sample_entry_point_spec",
        ]

        missing_fixtures = []
        for fixture in expected_fixtures:
            if f"def {fixture}" not in content:
                missing_fixtures.append(fixture)
            else:
                print(f"✅ Found fixture: {fixture}")

        if missing_fixtures:
            print("⚠️  Warning: Missing expected fixtures:")
            for missing in missing_fixtures:
                print(f"   - {missing}")
            # Don't fail for missing fixtures, just warn

        return True

    except Exception as e:
        print(f"❌ ERROR: Could not analyze conftest.py: {e}")
        return False


def main() -> int:
    """Main test completeness checker"""
    print("🔍 ansible-argument-spec-generator Test Completeness Checker")
    print("=" * 60)

    # Change to project root directory
    project_root = Path(__file__).parent.parent.parent
    import os

    os.chdir(project_root)

    checks = [
        ("Main Module Coverage", check_main_module_coverage),
        ("Test Function Coverage", check_test_function_coverage),
        ("Test Naming Conventions", check_test_naming_conventions),
        ("Test Categories Coverage", check_test_categories_coverage),
        ("Fixture Completeness", check_fixture_completeness),
    ]

    all_passed = True

    for check_name, check_func in checks:
        print(f"\n🧪 {check_name}")
        print("-" * 40)

        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"💥 {check_name} failed with exception: {e}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TEST COMPLETENESS CHECKS PASSED!")
        print("✅ Test suite appears comprehensive and well-structured")
        return 0
    else:
        print("💔 SOME TEST COMPLETENESS CHECKS FAILED")
        print("❌ Please address the issues above to ensure comprehensive testing")
        return 1


if __name__ == "__main__":
    sys.exit(main())
