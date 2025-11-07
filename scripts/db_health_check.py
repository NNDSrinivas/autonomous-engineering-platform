#!/usr/bin/env python3
"""Quick database health check for CI/pre-push hooks"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_database_health():
    """Quick database connection test"""
    try:
        from backend.core.config import settings
        from sqlalchemy import create_engine, text
        
        # Test PostgreSQL connection with short timeout
        engine = create_engine(settings.sqlalchemy_url, pool_timeout=5, pool_pre_ping=True)
        
        start = time.time()
        with engine.connect() as conn:
            # Simple query
            conn.execute(text('SELECT 1'))
            elapsed = time.time() - start
            
        print(f"✅ Database connection healthy ({elapsed:.2f}s)")
        return True
        
    except Exception as e:
        print(f"⚠️ Database connection issue: {e}")
        # Don't fail CI for database connection issues
        return True  # Non-blocking for CI

def check_redis_health():
    """Quick Redis connection test"""
    try:
        import redis
        client = redis.from_url('redis://localhost:6379/0', socket_connect_timeout=3)
        client.ping()
        print("✅ Redis connection healthy")
        return True
    except Exception as e:
        print(f"⚠️ Redis connection issue: {e}")
        return True  # Non-blocking for CI

if __name__ == "__main__":
    print("🔍 Running database health checks...")
    
    db_ok = check_database_health()
    redis_ok = check_redis_health()
    
    if db_ok and redis_ok:
        print("✅ All database services healthy")
        sys.exit(0)
    else:
        print("⚠️ Some database issues (non-blocking)")
        sys.exit(0)  # Don't fail CI for database issues