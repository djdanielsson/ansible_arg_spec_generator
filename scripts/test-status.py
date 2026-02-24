#!/usr/bin/env python3
"""
Test status checker for ansible-argument-spec-generator

Quick local test status check that mimics CI checks
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list, description: str) -> tuple[bool, str]:
    """Run a command and return success status and output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Command timed out: {' '.join(cmd)}"
    except Exception as e:
        return False, f"Failed to run command: {e}"


def check_test_status():
    """Check overall test status"""
    print("🔍 ansible-argument-spec-generator Test Status Check")
    print("=" * 60)

    project_root = Path(__file__).parent.parent
    import os

    os.chdir(project_root)

    checks = [
        {
            "name": "Basic Smoke Tests",
            "cmd": ["python", "tests/test_runner.py", "--basic"],
            "critical": True,
        },
        {
            "name": "Full Test Suite",
            "cmd": ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
            "critical": True,
        },
        {
            "name": "Test Completeness Check",
            "cmd": ["python", ".github/scripts/check_test_completeness.py"],
            "critical": False,
        },
        {
            "name": "Code Formatting (Black)",
            "cmd": ["python", "-m", "black", "--check", "--diff", "."],
            "critical": False,
        },
        {
            "name": "Code Linting (Flake8)",
            "cmd": [
                "python",
                "-m",
                "flake8",
                "generate_argument_specs/",
                "tests/",
                "--max-line-length=100",
                "--ignore=E203,W503",
            ],
            "critical": False,
        },
    ]

    results = []
    total_time = 0

    for check in checks:
        print(f"\n🧪 {check['name']}")
        print("-" * 40)

        start_time = time.time()
        success, output = run_command(check["cmd"], check["name"])
        end_time = time.time()
        duration = end_time - start_time
        total_time += duration

        results.append(
            {
                "name": check["name"],
                "success": success,
                "critical": check["critical"],
                "duration": duration,
                "output": output,
            }
        )

        if success:
            print(f"✅ PASSED ({duration:.1f}s)")
        else:
            print(f"❌ FAILED ({duration:.1f}s)")
            if check["critical"]:
                print("🚨 This is a critical check!")

        # Show output for failed checks
        if not success and output:
            print("\nOutput:")
            print("-" * 20)
            print(output.strip()[-500:])  # Last 500 chars
            print("-" * 20)

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST STATUS SUMMARY")
    print("=" * 60)

    total_checks = len(results)
    passed_checks = sum(1 for r in results if r["success"])
    critical_checks = [r for r in results if r["critical"]]
    critical_passed = sum(1 for r in critical_checks if r["success"])

    print(f"Total checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    print(f"Critical checks: {len(critical_checks)}")
    print(f"Critical passed: {critical_passed}")
    print(f"Total time: {total_time:.1f}s")

    # Detailed results
    print("\nDetailed Results:")
    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        critical_marker = "🚨" if result["critical"] and not result["success"] else "  "
        print(
            f"{critical_marker} {status} {result['name']} ({result['duration']:.1f}s)"
        )

    # Overall status
    all_critical_passed = all(r["success"] for r in critical_checks)
    all_passed = all(r["success"] for r in results)

    print("\n" + "=" * 60)

    if all_passed:
        print("🎉 ALL CHECKS PASSED!")
        print("✅ Ready for commit/push")
        return 0
    elif all_critical_passed:
        print("⚠️  CRITICAL CHECKS PASSED")
        print("✅ Safe to commit, but consider fixing non-critical issues")
        return 0
    else:
        print("💔 CRITICAL CHECKS FAILED")
        print("❌ Fix critical issues before committing")
        return 1


def check_quick_status():
    """Quick status check (just critical tests)"""
    print("⚡ Quick Test Status Check")
    print("=" * 40)

    project_root = Path(__file__).parent.parent
    import os

    os.chdir(project_root)

    # Run basic tests
    print("🚀 Running basic tests...")
    success, output = run_command(
        ["python", "tests/test_runner.py", "--basic"], "Basic Tests"
    )

    if success:
        print("✅ Basic tests PASSED")
    else:
        print("❌ Basic tests FAILED")
        print(output[-300:])  # Last 300 chars
        return 1

    # Check syntax
    print("🔍 Checking syntax...")
    success, output = run_command(
        ["python", "-c", "import generate_argument_specs"], "Import Check"
    )

    if success:
        print("✅ Syntax check PASSED")
    else:
        print("❌ Syntax check FAILED")
        print(output)
        return 1

    print("\n🎉 Quick checks PASSED!")
    return 0


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        return check_quick_status()
    else:
        return check_test_status()


if __name__ == "__main__":
    sys.exit(main())
