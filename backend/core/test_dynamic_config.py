"""
Test script for dynamic configuration loading

Run with: python -m backend.core.test_dynamic_config
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.config_loader import get_config_loader  # noqa: E402
from backend.core.dynamic_project_detector import get_project_detector  # noqa: E402


def test_intent_patterns():
    """Test loading intent patterns"""
    print("\n" + "=" * 80)
    print("Testing Intent Pattern Loading")
    print("=" * 80)

    loader = get_config_loader()
    patterns = loader.load_intent_patterns("english")

    print(f"\n✅ Loaded {len(patterns)} intent patterns")

    # Show first 5 patterns
    print("\nSample patterns:")
    for i, pattern in enumerate(patterns[:5], 1):
        print(f"\n{i}. Action: {pattern.action}")
        print(f"   Regex: {pattern.regex}")
        print(f"   Confidence: {pattern.confidence}")
        if pattern.examples:
            print(f"   Examples: {pattern.examples[:2]}")

    return len(patterns) > 0


def test_frameworks():
    """Test loading framework definitions"""
    print("\n" + "=" * 80)
    print("Testing Framework Definitions Loading")
    print("=" * 80)

    loader = get_config_loader()
    frameworks = loader.load_frameworks()

    print(f"\n✅ Loaded {len(frameworks)} framework definitions")

    # Show frameworks by category
    categories = {}
    for fw in frameworks:
        if fw.category not in categories:
            categories[fw.category] = []
        categories[fw.category].append(fw)

    print("\nFrameworks by category:")
    for category, fws in categories.items():
        print(f"\n{category.upper()}:")
        for fw in fws:
            print(f"  - {fw.display_name} (priority: {fw.priority})")

    return len(frameworks) > 0


def test_package_managers():
    """Test loading package manager definitions"""
    print("\n" + "=" * 80)
    print("Testing Package Manager Definitions Loading")
    print("=" * 80)

    loader = get_config_loader()
    package_managers = loader.load_package_managers()

    print(f"\n✅ Loaded {len(package_managers)} package manager definitions")

    # Show package managers by category
    categories = {}
    for pm in package_managers:
        if pm.category not in categories:
            categories[pm.category] = []
        categories[pm.category].append(pm)

    print("\nPackage managers by category:")
    for category, pms in categories.items():
        print(f"\n{category.upper()}:")
        for pm in pms:
            print(f"  - {pm.display_name} (priority: {pm.priority})")
            # Show sample commands
            if "install_package" in pm.commands:
                cmd = " ".join(pm.commands["install_package"])
                print(f"    Install: {cmd}")

    return len(package_managers) > 0


def test_project_detection():
    """Test project detection on current workspace"""
    print("\n" + "=" * 80)
    print("Testing Project Detection")
    print("=" * 80)

    detector = get_project_detector()

    # Test on current project
    workspace = str(project_root)
    print(f"\nDetecting project at: {workspace}")

    project_type, technologies, dependencies = detector.detect(workspace)

    print(f"\n✅ Project Type: {project_type}")
    print(f"✅ Technologies: {', '.join(technologies)}")
    print(f"✅ Dependencies Found: {len(dependencies)}")

    if dependencies:
        print("\nSample dependencies:")
        for dep, version in list(dependencies.items())[:5]:
            print(f"  - {dep}: {version}")

    return True


def test_config_info():
    """Test configuration information"""
    print("\n" + "=" * 80)
    print("Configuration Information")
    print("=" * 80)

    loader = get_config_loader()
    info = loader.get_config_info()

    print(f"\nConfig Directory: {info['config_dir']}")
    print(f"Loaded Configs: {', '.join(info['loaded_configs'])}")
    print(f"Cached Files: {info['cached_files']}")

    return True


def main():
    """Run all tests"""
    print("\n🚀 Testing Dynamic NAVI Configuration System")
    print("=" * 80)

    tests = [
        ("Intent Patterns", test_intent_patterns),
        ("Frameworks", test_frameworks),
        ("Package Managers", test_package_managers),
        ("Project Detection", test_project_detection),
        ("Config Info", test_config_info),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            results.append((test_name, False, str(e)))

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")

    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "=" * 80)

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
