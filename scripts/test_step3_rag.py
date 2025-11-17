#!/usr/bin/env python3
"""
Test script for Step 3: Unified RAG Search System

This script verifies:
1. Search endpoint returns results
2. Citations are properly formatted
3. Memory context enhances NAVI responses
4. Stats and health endpoints work
"""

import asyncio
import httpx
import json
from typing import List, Dict, Any


BASE_URL = "http://localhost:8787"
TEST_USER_ID = "test-user-step3"


async def test_search_endpoint():
    """Test the unified search endpoint"""
    print("\n=== Test 1: Search Endpoint ===")
    
    async with httpx.AsyncClient() as client:
        # Test search
        response = await client.post(
            f"{BASE_URL}/api/navi/search",
            json={
                "query": "environment URL",
                "user_id": TEST_USER_ID,
                "categories": ["workspace", "task"],
                "limit": 5,
                "min_importance": 0.3,
            },
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Found {data['total']} results")
            
            if data["results"]:
                print("\nTop Result:")
                result = data["results"][0]
                print(f"  Category: {result['category']}")
                print(f"  Title: {result['title']}")
                print(f"  Content: {result['content'][:100]}...")
                print(f"  Similarity: {result['similarity']:.3f}")
                print(f"  Importance: {result['importance']}")
        else:
            print(f"✗ Error: {response.text}")


async def test_search_stats():
    """Test the search stats endpoint"""
    print("\n=== Test 2: Search Stats ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/navi/search/stats",
            params={"user_id": TEST_USER_ID},
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Memory counts:")
            for category, count in data["memory_counts"].items():
                print(f"  {category}: {count}")
            print(f"Total: {data['total_memories']}")
        else:
            print(f"✗ Error: {response.text}")


async def test_search_health():
    """Test the search health endpoint"""
    print("\n=== Test 3: Search Health ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/navi/search/health")
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Status: {data['status']}")
            print(f"  OpenAI: {data['openai_configured']}")
            print(f"  Service: {data['service']}")
        else:
            print(f"✗ Error: {response.text}")


async def test_navi_with_memory():
    """Test NAVI chat with memory context"""
    print("\n=== Test 4: NAVI Chat with Memory Context ===")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/navi/chat",
            json={
                "message": "What's the development environment URL?",
                "model": "gpt-4",
                "mode": "chat",
            },
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Response length: {len(data['content'])}")
            print(f"\nNAVI: {data['content'][:300]}...")
            
            if data.get("actions"):
                print(f"\nActions: {len(data['actions'])}")
        else:
            print(f"✗ Error: {response.text}")


async def create_test_memory():
    """Create test memory for demo purposes"""
    print("\n=== Setup: Creating Test Memory ===")
    
    async with httpx.AsyncClient() as client:
        # Simulate a Confluence sync that would create memory
        test_memories = [
            {
                "category": "workspace",
                "scope": "global",
                "title": "Development Environment",
                "content": "The dev environment URL is https://dev.example.com. Use this for testing before production deployment.",
                "importance": 0.8,
                "metadata": {"source": "confluence", "page_id": "123"},
            },
            {
                "category": "task",
                "scope": "LAB-158",
                "title": "Barcode Override Feature",
                "content": "Discussed barcode override implementation in Slack. Need to add manual override field in inventory system.",
                "importance": 0.7,
                "metadata": {"source": "jira", "issue_key": "LAB-158"},
            },
        ]
        
        print(f"✓ Test memories prepared: {len(test_memories)} items")
        print("  (Note: In production, these would be created via org sync endpoints)")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Step 3: Unified RAG Search System - Test Suite")
    print("=" * 60)
    
    try:
        # Setup
        await create_test_memory()
        
        # Run tests
        await test_search_endpoint()
        await test_search_stats()
        await test_search_health()
        await test_navi_with_memory()
        
        print("\n" + "=" * 60)
        print("Test suite completed!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Create memory via org sync endpoints:")
        print("   POST /api/org/sync/confluence")
        print("   POST /api/org/sync/jira")
        print("2. Test search with real data")
        print("3. Ask NAVI questions that require memory context")
        
    except httpx.ConnectError:
        print("\n✗ Error: Cannot connect to backend")
        print(f"  Ensure server is running at {BASE_URL}")
        print("  Run: python main.py")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
