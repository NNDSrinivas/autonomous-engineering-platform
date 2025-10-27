#!/usr/bin/env python3
"""Seed PR-17 test fixture into memory graph database

Loads fixture JSON with 6-node chain (Meeting → Issue → PR → Deploy → Incident → Hotfix)
into memory_node and memory_edge tables for testing and demonstration.

Usage:
    python scripts/seed_graph_fixture.py data/seed/pr17_fixture.json
    
    # Or via Makefile:
    make pr17-seed
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models.memory_graph import MemoryNode, MemoryEdge, Base
from backend.core.config import settings

def load_fixture(fixture_path: str) -> Dict[str, Any]:
    """Load fixture JSON from file"""
    with open(fixture_path, 'r') as f:
        return json.load(f)

def seed_nodes(session, org_id: str, nodes: List[Dict[str, Any]]) -> Dict[str, int]:
    """Insert nodes and return mapping of foreign_id -> db_id"""
    foreign_id_map = {}
    
    print(f"\n📊 Seeding {len(nodes)} nodes...")
    
    for node_data in nodes:
        # Parse created_at if it's a string
        created_at = node_data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        node = MemoryNode(
            org_id=org_id,
            kind=node_data['kind'],
            foreign_id=node_data['foreign_id'],
            title=node_data['title'],
            summary=node_data.get('summary'),
            meta_json=node_data.get('meta_json', {}),
            created_at=created_at or datetime.utcnow(),
            updated_at=created_at or datetime.utcnow()
        )
        session.add(node)
        session.flush()  # Get ID assigned
        
        foreign_id_map[node_data['foreign_id']] = node.id
        print(f"  ✓ {node.kind:15} | {node.foreign_id:25} | ID={node.id}")
    
    return foreign_id_map

def seed_edges(session, org_id: str, edges: List[Dict[str, Any]], foreign_id_map: Dict[str, int]):
    """Insert edges using foreign_id mapping"""
    print(f"\n🔗 Seeding {len(edges)} edges...")
    
    edges_created = 0
    for edge_data in edges:
        src_foreign_id = edge_data['src_foreign_id']
        dst_foreign_id = edge_data['dst_foreign_id']
        
        if src_foreign_id not in foreign_id_map:
            print(f"  ⚠️  Skipping edge: source '{src_foreign_id}' not found")
            continue
        if dst_foreign_id not in foreign_id_map:
            print(f"  ⚠️  Skipping edge: destination '{dst_foreign_id}' not found")
            continue
        
        edge = MemoryEdge(
            org_id=org_id,
            src_id=foreign_id_map[src_foreign_id],
            dst_id=foreign_id_map[dst_foreign_id],
            relation=edge_data['relation'],
            weight=edge_data.get('weight', 1.0),
            confidence=edge_data.get('confidence', 1.0),
            meta_json=edge_data.get('meta_json', {})
        )
        session.add(edge)
        edges_created += 1
        
        print(f"  ✓ {src_foreign_id:20} --[{edge.relation:12}]--> {dst_foreign_id:20}")
    
    print(f"\n✅ Created {edges_created} edges")

def clear_existing_data(session, org_id: str):
    """Remove existing PR-17 test data"""
    print(f"\n🗑️  Clearing existing data for org '{org_id}'...")
    
    # Delete edges first (foreign key constraints)
    edges_deleted = session.query(MemoryEdge).filter(MemoryEdge.org_id == org_id).delete()
    nodes_deleted = session.query(MemoryNode).filter(MemoryNode.org_id == org_id).delete()
    
    session.commit()
    print(f"  Deleted {edges_deleted} edges, {nodes_deleted} nodes")

def verify_seeded_data(session, org_id: str, expected: Dict[str, Any]):
    """Verify seeded data matches expectations"""
    print(f"\n✓ Verifying seeded data...")
    
    node_count = session.query(MemoryNode).filter(MemoryNode.org_id == org_id).count()
    edge_count = session.query(MemoryEdge).filter(MemoryEdge.org_id == org_id).count()
    
    expected_nodes = expected.get('total_nodes', 0)
    expected_edges = expected.get('total_edges', 0)
    
    print(f"  Nodes: {node_count} (expected: {expected_nodes}) {'✓' if node_count == expected_nodes else '✗'}")
    print(f"  Edges: {edge_count} (expected: {expected_edges}) {'✓' if edge_count == expected_edges else '✗'}")
    
    if node_count != expected_nodes or edge_count != expected_edges:
        print(f"\n⚠️  WARNING: Actual counts don't match expected!")
        return False
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_graph_fixture.py <fixture_json_path>")
        print("Example: python scripts/seed_graph_fixture.py data/seed/pr17_fixture.json")
        sys.exit(1)
    
    fixture_path = sys.argv[1]
    
    if not Path(fixture_path).exists():
        print(f"❌ Fixture file not found: {fixture_path}")
        sys.exit(1)
    
    print(f"🌱 PR-17 Graph Fixture Seeder")
    print(f"=" * 60)
    print(f"Fixture: {fixture_path}")
    
    # Load fixture
    fixture = load_fixture(fixture_path)
    org_id = fixture.get('org_id', 'default')
    print(f"Org ID:  {org_id}")
    print(f"Description: {fixture.get('description', 'N/A')}")
    
    # Connect to database
    db_url = settings.database_url or f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    engine = create_engine(db_url)
    
    # Create tables if they don't exist
    print("📋 Creating tables if needed...")
    Base.metadata.create_all(engine)
    print()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Clear existing data
        clear_existing_data(session, org_id)
        
        # Seed nodes
        foreign_id_map = seed_nodes(session, org_id, fixture['nodes'])
        session.commit()
        
        # Seed edges
        seed_edges(session, org_id, fixture['edges'], foreign_id_map)
        session.commit()
        
        # Verify
        success = verify_seeded_data(session, org_id, fixture.get('expected_metrics', {}))
        
        if success:
            print(f"\n✅ SUCCESS: Fixture seeded successfully!")
            print(f"\nNext steps:")
            print(f"  1. Run smoke tests:  make pr17-smoke")
            print(f"  2. Run test suite:   pytest tests/test_graph_*.py")
            print(f"  3. View in VS Code:  aep.openTimeline (ENG-102)")
        else:
            print(f"\n⚠️  Seeding completed with warnings")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == '__main__':
    main()
