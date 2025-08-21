#!/usr/bin/env python3
"""
Test runner for ansible-argument-spec-generator

This script runs all tests and provides a summary of results.
Can be used for development and CI/CD pipelines.
"""

import sys
import subprocess
import time
from pathlib import Path


def run_tests():
    """Run all tests and return results"""
    test_results = {}
    test_dir = Path(__file__).parent

    # List of test modules to run
    test_modules = [
        "test_basic.py",
        "test_argument_spec.py",
        "test_generator_core.py",
        "test_variable_extraction.py",
        "test_integration.py",
        "test_edge_cases.py",
        "test_type_inference.py",
    ]

    print("🧪 Running ansible-argument-spec-generator test suite")
    print("=" * 60)

    total_start_time = time.time()

    for test_module in test_modules:
        test_file = test_dir / test_module

        if not test_file.exists():
            print(f"⚠️  Test file {test_module} not found, skipping...")
            continue

        print(f"\n📋 Running {test_module}...")
        start_time = time.time()

        try:
            # Run pytest on the specific module
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=test_dir.parent,
            )

            end_time = time.time()
            duration = end_time - start_time

            test_results[test_module] = {
                "success": result.returncode == 0,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result.returncode == 0:
                print(f"✅ {test_module} passed ({duration:.2f}s)")
            else:
                print(f"❌ {test_module} failed ({duration:.2f}s)")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")

        except Exception as e:
            test_results[test_module] = {
                "success": False,
                "duration": 0,
                "error": str(e),
            }
            print(f"💥 {test_module} crashed: {e}")

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time

    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for result in test_results.values() if result["success"])
    total = len(test_results)

    print(f"Tests run: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Total duration: {total_duration:.2f}s")

    if passed == total:
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n💔 {total - passed} test(s) failed")

        # Show details of failed tests
        for test_name, result in test_results.items():
            if not result["success"]:
                print(f"\n❌ {test_name}:")
                if "error" in result:
                    print(f"   Exception: {result['error']}")
                elif result.get("stderr"):
                    print(f"   Error: {result['stderr'].strip()}")

        return False


def run_basic_tests_only():
    """Run only basic smoke tests for quick verification"""
    test_dir = Path(__file__).parent
    basic_test = test_dir / "test_basic.py"

    print("🚀 Running basic smoke tests...")

    try:
        # Try running the basic tests directly first
        result = subprocess.run(
            [sys.executable, str(basic_test)],
            capture_output=True,
            text=True,
            cwd=test_dir.parent,
        )

        if result.returncode == 0:
            print("✅ Basic tests passed!")
            print(result.stdout)
            return True
        else:
            print("❌ Basic tests failed!")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return False

    except Exception as e:
        print(f"💥 Failed to run basic tests: {e}")
        return False


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--basic":
        return run_basic_tests_only()
    else:
        return run_tests()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
