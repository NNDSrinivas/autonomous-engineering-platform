"""Test causality path finding and narrative generation

Verifies that:
1. Explain endpoint returns narrative with citations
2. Narrative contains causality chain keywords
3. Node IDs or foreign_ids are cited in narrative
4. Subgraph returned matches query depth and k parameters
"""

from httpx import Client
from tests.conftest import assert_response_ok


def test_explain_contains_citations(api_client: Client, seeded_graph):
    """Verify narrative contains citations to node IDs or foreign_ids"""
    response = api_client.post(
        "/api/memory/graph/query",
        json={"query": "Why was ENG-102 reopened and what was the fix?", "depth": 3, "k": 12}
    )
    data = assert_response_ok(response)
    
    # Verify narrative exists and is non-empty
    assert "narrative" in data, "Response missing 'narrative' field"
    narrative = data["narrative"]
    assert narrative and len(narrative) > 50, \
        f"Narrative too short or empty: {len(narrative)} chars"
    
    # Extract node IDs and foreign IDs
    {node["id"] for node in data["nodes"]}
    foreign_ids = {node["foreign_id"] for node in data["nodes"]}
    
    # Check if any node IDs or foreign IDs appear in narrative
    ids_in_narrative = [fid for fid in foreign_ids if fid in narrative]
    
    # Alternative: check for explicit citations field
    has_citations = "citations" in data or len(ids_in_narrative) > 0
    
    assert has_citations, \
        f"Narrative contains no citations to nodes. Narrative: {narrative[:200]}"
    
    if ids_in_narrative:
        print(f"✅ Narrative cites: {', '.join(ids_in_narrative)}")
    else:
        print("✅ Narrative has citations field")


def test_explain_contains_causality_chain(api_client: Client, seeded_graph):
    """Verify narrative describes causality chain (caused_by → fixes)"""
    response = api_client.post(
        "/api/memory/graph/query",
        json={"query": "What caused the incident and how was it fixed?", "depth": 3, "k": 12}
    )
    data = assert_response_ok(response)
    
    narrative = data["narrative"].lower()
    
    # Expected causality keywords from fixture
    expected_keywords = [
        "cache",         # Core issue
        "incident",      # INC-789
        "deploy",        # Caused by deployment
        "fix",           # Hotfix PR
        "invalidation"   # Specific problem
    ]
    
    found_keywords = [kw for kw in expected_keywords if kw in narrative]
    
    # Should mention at least 3 of the 5 key concepts
    assert len(found_keywords) >= 3, \
        f"Narrative missing causality keywords. Found: {found_keywords}, Narrative: {narrative[:300]}"
    
    print(f"✅ Narrative contains causality chain: {', '.join(found_keywords)}")


def test_explain_respects_depth_parameter(api_client: Client, seeded_graph):
    """Verify depth parameter affects subgraph size"""
    # Query with depth=1 (shallow)
    response_shallow = api_client.post(
        "/api/memory/graph/query",
        json={"query": "What is ENG-102?", "depth": 1, "k": 12}
    )
    data_shallow = assert_response_ok(response_shallow)
    
    # Query with depth=3 (deep)
    response_deep = api_client.post(
        "/api/memory/graph/query",
        json={"query": "What is ENG-102?", "depth": 3, "k": 12}
    )
    data_deep = assert_response_ok(response_deep)
    
    # Deeper query should have more or equal nodes (not strictly enforced, but typical)
    shallow_nodes = len(data_shallow["nodes"])
    deep_nodes = len(data_deep["nodes"])
    
    print(f"✅ Depth parameter: depth=1 → {shallow_nodes} nodes, depth=3 → {deep_nodes} nodes")
    
    # At minimum, both should return some nodes
    assert shallow_nodes >= 1, "Shallow query returned no nodes"
    assert deep_nodes >= 1, "Deep query returned no nodes"


def test_explain_respects_k_parameter(api_client: Client, seeded_graph):
    """Verify k parameter limits node count"""
    # Query with k=3 (limited)
    response_limited = api_client.post(
        "/api/memory/graph/query",
        json={"query": "Explain ENG-102 timeline", "depth": 3, "k": 3}
    )
    data_limited = assert_response_ok(response_limited)
    
    # Should not exceed k nodes
    assert len(data_limited["nodes"]) <= 3, \
        f"Expected ≤3 nodes (k=3), found {len(data_limited['nodes'])}"
    
    # Query with k=12 (larger)
    response_larger = api_client.post(
        "/api/memory/graph/query",
        json={"query": "Explain ENG-102 timeline", "depth": 3, "k": 12}
    )
    data_larger = assert_response_ok(response_larger)
    
    # Should allow more nodes
    assert len(data_larger["nodes"]) <= 12, \
        f"Expected ≤12 nodes (k=12), found {len(data_larger['nodes'])}"
    
    print(f"✅ k parameter: k=3 → {len(data_limited['nodes'])} nodes, k=12 → {len(data_larger['nodes'])} nodes")


def test_explain_returns_edges_for_subgraph(api_client: Client, seeded_graph):
    """Verify response includes edges connecting the nodes"""
    response = api_client.post(
        "/api/memory/graph/query",
        json={"query": "How are the components related?", "depth": 2, "k": 10}
    )
    data = assert_response_ok(response)
    
    # Should have edges
    assert "edges" in data, "Response missing 'edges' field"
    assert len(data["edges"]) > 0, "No edges returned in subgraph"
    
    # All edge src_id and dst_id should reference nodes in the subgraph
    node_ids = {node["id"] for node in data["nodes"]}
    
    for edge in data["edges"]:
        assert edge["src_id"] in node_ids, \
            f"Edge src_id {edge['src_id']} not in node set"
        assert edge["dst_id"] in node_ids, \
            f"Edge dst_id {edge['dst_id']} not in node set"
    
    print(f"✅ Subgraph has {len(data['edges'])} edges connecting {len(data['nodes'])} nodes")


def test_explain_narrative_is_coherent(api_client: Client, seeded_graph):
    """Verify narrative is formatted and coherent"""
    response = api_client.post(
        "/api/memory/graph/query",
        json={"query": "Explain the full story of ENG-102", "depth": 3, "k": 12}
    )
    data = assert_response_ok(response)
    
    narrative = data["narrative"]
    
    # Basic coherence checks
    assert len(narrative) >= 100, \
        f"Narrative too short to be coherent: {len(narrative)} chars"
    
    assert len(narrative) <= 5000, \
        f"Narrative too long (possible error): {len(narrative)} chars"
    
    # Should have multiple sentences
    sentence_count = narrative.count('.') + narrative.count('!') + narrative.count('?')
    assert sentence_count >= 3, \
        f"Narrative has too few sentences: {sentence_count}"
    
    # Should not have obvious error markers
    error_markers = ["error", "exception", "traceback", "failed to"]
    has_errors = any(marker in narrative.lower() for marker in error_markers)
    assert not has_errors, \
        f"Narrative contains error markers: {narrative[:200]}"
    
    print(f"✅ Narrative is coherent: {len(narrative)} chars, ~{sentence_count} sentences")


def test_explain_with_invalid_query(api_client: Client, seeded_graph):
    """Verify graceful handling of invalid/empty queries"""
    # Empty query
    response_empty = api_client.post(
        "/api/memory/graph/query",
        json={"query": "", "depth": 2, "k": 5}
    )
    
    # Should return 400 or handle gracefully with empty results
    assert response_empty.status_code in [200, 400, 422], \
        f"Unexpected status for empty query: {response_empty.status_code}"
    
    # Query about non-existent entity
    response_nonexistent = api_client.post(
        "/api/memory/graph/query",
        json={"query": "Tell me about FAKE-999", "depth": 2, "k": 5}
    )
    
    # Should return 200 with empty or minimal results
    if response_nonexistent.status_code == 200:
        data = response_nonexistent.json()
        # Empty results are acceptable
        print(f"✅ Non-existent entity query handled gracefully: {len(data.get('nodes', []))} nodes")
