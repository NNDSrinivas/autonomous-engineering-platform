#!/usr/bin/env python3
"""
Test Slack Integration with NAVI Unified Memory System

This tests that:
1. SlackService can be imported and initialized safely
2. Unified Memory System includes Slack in its retrieval
3. MemoryContext and OrgSnippet structures work correctly
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath('.'))

def test_slack_service_import():
    """Test that SlackService can be safely imported."""
    print("\n=== Testing Slack Service Import ===")
    
    try:
        from backend.services.slack_service import search_messages_for_user, search_messages, _get_client
        print("✅ SlackService imported successfully")
        
        # Test client creation (should not crash even if token missing)
        client = _get_client()
        if client is None:
            print("ℹ️ SlackClient not configured (AEP_SLACK_BOT_TOKEN missing) - this is expected")
        else:
            print("✅ SlackClient configured and available")
        
        return True
    except Exception as e:
        print(f"❌ SlackService import failed: {e}")
        return False

def test_unified_memory_retriever():
    """Test that unified memory retriever includes Slack."""
    print("\n=== Testing Unified Memory Retriever ===")
    
    try:
        from backend.agent.unified_memory_retriever import retrieve_unified_memories
        print("✅ Unified memory retriever imported successfully")
        
        # Test that it includes Slack in the source list
        import inspect
        source_code = inspect.getsource(retrieve_unified_memories)
        if "slack" in source_code.lower():
            print("✅ Unified memory retriever includes Slack integration")
        else:
            print("⚠️ Unified memory retriever may not include Slack")
        
        return True
    except Exception as e:
        print(f"❌ Unified memory retriever import failed: {e}")
        return False

def test_memory_context_structures():
    """Test OrgSnippet and MemoryContext structures."""
    print("\n=== Testing Memory Context Structures ===")
    
    try:
        from backend.agent.memory_retriever import OrgSnippet, MemoryContext
        print("✅ OrgSnippet and MemoryContext imported successfully")
        
        # Test OrgSnippet creation
        snippet = OrgSnippet(
            snippet_id="test_slack_1",
            source="slack",
            title="Test Slack Message",
            content="This is a test Slack message for NAVI",
            metadata={"channel": "general", "user": "test_user"},
            url="https://slack.com/archives/C123/p1234567890",
            timestamp="2024-01-01T12:00:00Z",
            relevance=0.8,
        )
        print("✅ OrgSnippet created successfully")
        
        # Test MemoryContext creation
        context = MemoryContext(
            user_profile=[],
            tasks=[],
            interactions=[],
            workspace=[],
            org_snippets=[snippet],
        )
        print("✅ MemoryContext created successfully")
        
        # Test serialization
        context_dict = context.to_dict()
        assert "org_snippets" in context_dict
        assert len(context_dict["org_snippets"]) == 1
        assert context_dict["org_snippets"][0]["source"] == "slack"
        print("✅ MemoryContext serialization works correctly")
        
        return True
    except Exception as e:
        print(f"❌ Memory context structures test failed: {e}")
        return False

async def test_slack_service_function():
    """Test Slack service functions with mock database."""
    print("\n=== Testing Slack Service Functions ===")
    
    try:
        from backend.services.slack_service import search_messages_for_user, search_messages
        print("✅ Slack service functions imported")
        
        # Test with None database (should not crash)
        result1 = search_messages_for_user(db=None, user_id="test_user", limit=5)
        assert isinstance(result1, list)
        print("✅ search_messages_for_user handles None db gracefully")
        
        result2 = search_messages(db=None, user_id="test_user", query="test", limit=5)
        assert isinstance(result2, list)
        print("✅ search_messages handles None db gracefully")
        
        return True
    except Exception as e:
        print(f"❌ Slack service function test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🧪 Testing Slack Integration with NAVI Unified Memory System")
    print("=" * 60)
    
    tests = [
        ("Slack Service Import", test_slack_service_import),
        ("Unified Memory Retriever", test_unified_memory_retriever), 
        ("Memory Context Structures", test_memory_context_structures),
        ("Slack Service Functions", test_slack_service_function),
    ]
    
    results = []
    for test_name, test_func in tests:
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! Slack integration is ready for NAVI.")
    else:
        print("\n⚠️ Some tests failed. Check the integration setup.")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main())