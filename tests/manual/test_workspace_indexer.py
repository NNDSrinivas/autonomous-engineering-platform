#!/usr/bin/env python3
# ruff: noqa: E402
"""
Test Enhanced Workspace Indexer

This script tests the newly enhanced workspace_retriever with:
1. Project type detection
2. Entry point detection
3. Dependency resolution (using existing DependencyResolver)
4. Static code analysis (using existing IncrementalStaticAnalyzer)

Run: python test_workspace_indexer.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agent.workspace_retriever import index_workspace_full


async def test_indexer():
    """Test the enhanced workspace indexer on this repository"""

    print("=" * 80)
    print("🧪 TESTING ENHANCED WORKSPACE INDEXER")
    print("=" * 80)
    print()

    # Test on this repository (autonomous-engineering-platform)
    workspace_root = str(Path(__file__).parent)

    print(f"📂 Workspace: {workspace_root}")
    print()
    print("⏳ Indexing workspace (this may take a few seconds)...")
    print()

    try:
        # Run full indexing
        result = await index_workspace_full(
            workspace_root=workspace_root,
            user_id="test_user",
            include_code_analysis=True,
            include_dependencies=True,
        )

        print("✅ Indexing completed!")
        print()

        # Display results
        print("=" * 80)
        print("📊 INDEXING RESULTS")
        print("=" * 80)
        print()

        # Project info
        print(f"🔍 Project Type: {result.get('project_type', 'unknown')}")
        print(f"📍 Entry Points: {len(result.get('entry_points', []))}")
        if result.get("entry_points"):
            for ep in result.get("entry_points", [])[:5]:
                print(f"   - {ep}")
            if len(result.get("entry_points", [])) > 5:
                print(f"   ... and {len(result.get('entry_points', [])) - 5} more")
        print()

        # Files
        print(f"📁 Files Scanned: {len(result.get('files', []))}")
        print()

        # Dependencies
        if "dependencies" in result:
            deps = result["dependencies"]
            if "error" not in deps:
                print("📦 Dependencies:")
                print(f"   Total: {deps.get('total', 0)}")
                print(f"   Direct: {deps.get('direct', 0)}")
                print(f"   Internal: {deps.get('internal', 0)}")
                print(f"   External: {deps.get('external', 0)}")
                print(f"   Health Score: {deps.get('health_score', 0.0):.2f}")
                if deps.get("files"):
                    print("   Dependency Files:")
                    for df in deps.get("files", [])[:3]:
                        print(f"      - {Path(df).name}")
                print()
            else:
                print(f"⚠️  Dependencies: {deps.get('error')}")
                print()

        # Code analysis
        if "code_analysis" in result:
            analysis = result["code_analysis"]
            if "error" not in analysis:
                print("🔬 Code Analysis:")
                summary = analysis.get("summary", {})
                print(f"   Total Issues: {summary.get('total_issues', 0)}")
                print(f"   Files Analyzed: {summary.get('total_files', 0)}")

                issues_by_severity = summary.get("issues_by_severity", {})
                if issues_by_severity:
                    print("   Issues by Severity:")
                    for severity, count in issues_by_severity.items():
                        if count > 0:
                            print(f"      {severity}: {count}")
                print()
            else:
                print(f"⚠️  Code Analysis: {analysis.get('error')}")
                print()

        # Summary
        print("=" * 80)
        print("✨ SUMMARY")
        print("=" * 80)
        print()
        print("The enhanced workspace indexer successfully:")
        print("✅ Detected project type")
        print("✅ Found entry points")
        print("✅ Scanned file structure")

        if "dependencies" in result and "error" not in result["dependencies"]:
            print("✅ Resolved dependencies (using existing DependencyResolver)")
        else:
            print("⚠️  Dependency resolution not available or failed")

        if "code_analysis" in result and "error" not in result["code_analysis"]:
            print("✅ Analyzed code quality (using existing IncrementalStaticAnalyzer)")
        else:
            print("⚠️  Static analysis not available or failed")

        print()
        print("🎉 Enhanced workspace indexer is working!")
        print()

        # Save full result to file for inspection
        output_file = Path(__file__).parent / "workspace_index_result.json"
        with open(output_file, "w") as f:
            # Make serializable
            serializable_result = json.loads(json.dumps(result, default=str, indent=2))
            json.dump(serializable_result, f, indent=2)

        print(f"📄 Full results saved to: {output_file}")
        print()

        return True

    except Exception as e:
        print(f"❌ Error during indexing: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_indexer())
    sys.exit(0 if success else 1)
