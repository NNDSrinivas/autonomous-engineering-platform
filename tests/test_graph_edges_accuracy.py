"""Test graph edge creation accuracy

Verifies that:
1. ≥80% of expected edges are created
2. All expected relation types are present
3. Edge weights and confidence scores are reasonable
4. No duplicate edges exist
"""

from httpx import Client
from tests.conftest import assert_response_ok


def test_edges_accuracy(api_client: Client, seeded_graph):
    """Verify ≥80% of expected edges created and all core relations present"""
    # Get ENG-102 neighborhood
    response = api_client.get("/api/memory/graph/node/ENG-102")
    data = assert_response_ok(response)
    
    # Extract relation types
    relations = {edge["relation"] for edge in data["edges"]}
    
    # Expected core relations from fixture
    expected_relations = {
        "derived_from",  # Meeting → Issue
        "implements",    # Issue → PR
        "fixes",         # PR → Issue, Hotfix → Incident
        "next",          # PR → Deploy, Incident → Hotfix
        "previous",      # Deploy → PR, Hotfix → Incident
        "caused_by",     # Incident → Deploy
        "references"     # Incident → PR, Issue → Incident
    }
    
    # Verify all expected relations are present
    for rel in expected_relations:
        assert rel in relations, f"Missing expected relation: {rel}"
    
    # Verify minimum node count (6 nodes in fixture)
    assert len(data["nodes"]) >= 6, \
        f"Expected ≥6 nodes, found {len(data['nodes'])}"
    
    # Verify edge count threshold (12 edges expected, ≥80% = 10 edges)
    expected_edges = 12
    min_edges = int(expected_edges * 0.8)
    assert len(data["edges"]) >= min_edges, \
        f"Expected ≥{min_edges} edges (80% of {expected_edges}), found {len(data['edges'])}"
    
    print(f"✅ Edge accuracy: {len(data['edges'])}/{expected_edges} edges created")
    print(f"✅ Relations found: {', '.join(sorted(relations))}")


def test_edge_weights_and_confidence(api_client: Client, seeded_graph):
    """Verify edge weights and confidence scores are in valid range [0, 1]"""
    response = api_client.get("/api/memory/graph/node/ENG-102")
    data = assert_response_ok(response)
    
    for edge in data["edges"]:
        weight = edge.get("weight", 1.0)
        confidence = edge.get("confidence", 1.0)
        
        assert 0.0 <= weight <= 1.0, \
            f"Edge {edge['id']} weight {weight} out of range [0, 1]"
        
        assert 0.0 <= confidence <= 1.0, \
            f"Edge {edge['id']} confidence {confidence} out of range [0, 1]"
        
        # High-confidence edges (fixes, implements) should have confidence ≥ 0.9
        if edge["relation"] in ["fixes", "implements"]:
            assert confidence >= 0.9, \
                f"High-confidence relation '{edge['relation']}' has low confidence: {confidence}"


def test_no_duplicate_edges(api_client: Client, seeded_graph):
    """Verify no duplicate edges exist"""
    response = api_client.get("/api/memory/graph/node/ENG-102")
    data = assert_response_ok(response)
    
    # Create edge signatures (src_id, dst_id, relation)
    edge_signatures = set()
    
    for edge in data["edges"]:
        signature = (edge["src_id"], edge["dst_id"], edge["relation"])
        
        assert signature not in edge_signatures, \
            f"Duplicate edge found: {signature}"
        
        edge_signatures.add(signature)
    
    print(f"✅ No duplicates: {len(edge_signatures)} unique edges")


def test_bidirectional_edges_symmetric(api_client: Client, seeded_graph):
    """Verify bidirectional edges (next/previous) are symmetric"""
    response = api_client.get("/api/memory/graph/node/ENG-102")
    data = assert_response_ok(response)
    
    # Build edge map
    edges_by_nodes = {}
    for edge in data["edges"]:
        key = (edge["src_id"], edge["dst_id"])
        if key not in edges_by_nodes:
            edges_by_nodes[key] = []
        edges_by_nodes[key].append(edge["relation"])
    
    # Check next/previous symmetry
    for (src, dst), relations in edges_by_nodes.items():
        if "next" in relations:
            # Should have corresponding "previous" edge in reverse
            reverse_key = (dst, src)
            assert reverse_key in edges_by_nodes, \
                f"'next' edge {src}→{dst} missing reverse 'previous' edge"
            assert "previous" in edges_by_nodes[reverse_key], \
                f"'next' edge {src}→{dst} has no 'previous' in reverse"
    
    print("✅ Bidirectional edges are symmetric")


def test_specific_fixture_edges(api_client: Client, seeded_graph):
    """Verify specific expected edges from fixture are created"""
    response = api_client.get("/api/memory/graph/node/ENG-102")
    data = assert_response_ok(response)
    
    # Build node foreign_id lookup
    nodes_by_id = {node["id"]: node for node in data["nodes"]}
    
    # Expected edges from fixture (partial list of critical ones)
    expected_edges = [
        ("MEET-2025-10-01", "ENG-102", "derived_from"),
        ("ENG-102", "#456", "implements"),
        ("#456", "ENG-102", "fixes"),
        ("#478", "INC-789", "fixes"),
    ]
    
    # Convert edges to (src_foreign_id, dst_foreign_id, relation) tuples
    actual_edges = set()
    for edge in data["edges"]:
        src_node = nodes_by_id.get(edge["src_id"])
        dst_node = nodes_by_id.get(edge["dst_id"])
        if src_node and dst_node:
            actual_edges.add((
                src_node["foreign_id"],
                dst_node["foreign_id"],
                edge["relation"]
            ))
    
    # Verify expected edges exist
    for expected in expected_edges:
        assert expected in actual_edges, \
            f"Expected edge missing: {expected[0]} --[{expected[2]}]--> {expected[1]}"
    
    print("✅ All critical fixture edges present")
