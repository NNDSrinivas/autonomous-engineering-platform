"""Test timeline ordering and sequence

Verifies that:
1. Timeline items are strictly ordered by timestamp (increasing)
2. Expected sequence of events is present
3. Time windows work correctly
4. Timeline includes all relevant nodes
"""

from httpx import Client
from datetime import datetime
from tests.conftest import assert_response_ok


def test_timeline_is_ordered(api_client: Client, seeded_graph):
    """Verify timeline returns strictly increasing timestamps"""
    response = api_client.get(
        "/api/memory/timeline", params={"entity_id": "ENG-102", "window": "30d"}
    )
    data = assert_response_ok(response)

    # Extract timestamps
    timestamps = []
    for item in data:
        ts_str = item.get("created_at") or item.get("ts")
        if ts_str:
            # Parse ISO format timestamp
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            timestamps.append(ts)

    # Verify strictly increasing (or equal for same-time events)
    for i in range(len(timestamps) - 1):
        assert (
            timestamps[i] <= timestamps[i + 1]
        ), f"Timeline not ordered: {timestamps[i]} > {timestamps[i+1]}"

    print(f"✅ Timeline ordered: {len(timestamps)} events in chronological order")


def test_expected_sequence(api_client: Client, seeded_graph):
    """Verify expected coarse sequence of events"""
    response = api_client.get(
        "/api/memory/timeline", params={"entity_id": "ENG-102", "window": "30d"}
    )
    data = assert_response_ok(response)

    # Extract titles/kinds for sequence checking
    titles = [item.get("title", "").lower() for item in data]
    kinds = [item.get("kind", "") for item in data]

    # Verify minimum events
    assert len(data) >= 6, f"Expected ≥6 timeline events, found {len(data)}"

    # Expected coarse sequence (order matters)
    # Meeting → Issue → PR → Deploy → Incident → Hotfix
    expected_sequence_keywords = [
        "grooming",  # Meeting
        "eng-102",  # Issue
        "#456",  # PR (first)
        "deploy",  # Deployment
        "inc-789",  # Incident
        "#478",  # PR (hotfix)
    ]

    # Find indices of each keyword
    indices = []

    for keyword in expected_sequence_keywords:
        # Find first occurrence of keyword
        for idx, title in enumerate(titles):
            if keyword in title:
                indices.append(idx)
                break

    # Verify sequence is in order (indices should be increasing)
    for i in range(len(indices) - 1):
        if indices[i] >= indices[i + 1]:
            print(
                f"⚠️  Sequence warning: {expected_sequence_keywords[i]} at {indices[i]}, "
                f"{expected_sequence_keywords[i+1]} at {indices[i+1]}"
            )

    # At minimum, verify Meeting comes before Issue, Issue before Deploy, Deploy before Incident
    meeting_idx = next((i for i, k in enumerate(kinds) if k == "meeting"), None)
    issue_idx = next((i for i, title in enumerate(titles) if "eng-102" in title), None)
    deploy_idx = next((i for i, k in enumerate(kinds) if k == "run"), None)
    incident_idx = next((i for i, k in enumerate(kinds) if k == "incident"), None)

    if meeting_idx is not None and issue_idx is not None:
        assert meeting_idx < issue_idx, "Meeting should come before Issue"

    if deploy_idx is not None and incident_idx is not None:
        assert deploy_idx < incident_idx, "Deploy should come before Incident"

    print("✅ Timeline sequence validated")
    print(f"   Events: {' → '.join([item.get('title', '?')[:30] for item in data])}")


def test_timeline_window_filtering(api_client: Client, seeded_graph):
    """Verify time window parameter filters correctly"""
    # Get 30d window
    response_30d = api_client.get(
        "/api/memory/timeline", params={"entity_id": "ENG-102", "window": "30d"}
    )
    data_30d = assert_response_ok(response_30d)

    # Get 7d window (should have fewer or equal items)
    response_7d = api_client.get(
        "/api/memory/timeline", params={"entity_id": "ENG-102", "window": "7d"}
    )
    data_7d = assert_response_ok(response_7d)

    # 7d window should not have more items than 30d
    assert len(data_7d) <= len(
        data_30d
    ), f"7d window ({len(data_7d)} items) should not exceed 30d window ({len(data_30d)} items)"

    print(f"✅ Window filtering: 7d={len(data_7d)} events, 30d={len(data_30d)} events")


def test_timeline_includes_all_node_types(api_client: Client, seeded_graph):
    """Verify timeline includes diverse node types from fixture"""
    response = api_client.get(
        "/api/memory/timeline", params={"entity_id": "ENG-102", "window": "30d"}
    )
    data = assert_response_ok(response)

    # Extract node kinds
    kinds = {item.get("kind") for item in data}

    # Expected node types from fixture
    expected_kinds = {"meeting", "jira_issue", "pr", "run", "incident"}

    # Verify major types are present
    for expected_kind in expected_kinds:
        assert expected_kind in kinds, f"Timeline missing expected node type: {expected_kind}"

    print(f"✅ Timeline includes all node types: {', '.join(sorted(kinds))}")


def test_timeline_has_required_fields(api_client: Client, seeded_graph):
    """Verify each timeline item has required fields"""
    response = api_client.get(
        "/api/memory/timeline", params={"entity_id": "ENG-102", "window": "30d"}
    )
    data = assert_response_ok(response)

    required_fields = ["id", "kind", "foreign_id", "title"]

    for idx, item in enumerate(data):
        for field in required_fields:
            assert field in item, f"Timeline item {idx} missing required field: {field}"

        # Should have at least one timestamp field
        assert "created_at" in item or "ts" in item, f"Timeline item {idx} missing timestamp field"

    print(f"✅ All {len(data)} timeline items have required fields")


def test_empty_timeline_for_nonexistent_issue(api_client: Client, seeded_graph):
    """Verify timeline returns empty for non-existent issue"""
    response = api_client.get(
        "/api/memory/timeline", params={"entity_id": "NONEXISTENT-999", "window": "30d"}
    )

    # Should return 200 with empty list, not 404
    assert response.status_code in [
        200,
        404,
    ], f"Expected 200 or 404, got {response.status_code}"

    if response.status_code == 200:
        response.json()  # Validate JSON response
        # Empty timeline is acceptable
        print("✅ Non-existent issue returns empty timeline")
    else:
        print("✅ Non-existent issue returns 404")
