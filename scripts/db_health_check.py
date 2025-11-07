#!/usr/bin/env python3
"""Quick database health check for CI/pre-push hooks"""

import os
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
        return False  # Return actual failure status

def check_redis_health():
    """Quick Redis connection test"""
    try:
        from backend.core.config import settings
        import redis
        
        # Use Redis URL from settings instead of hardcoded localhost
        client = redis.from_url(settings.redis_url, socket_connect_timeout=3)
        client.ping()
        print("✅ Redis connection healthy")
        return True
    except Exception as e:
        print(f"⚠️ Redis connection issue: {e}")
        return False  # Return actual failure status

if __name__ == "__main__":
    print("🔍 Running database health checks...")
    
    db_ok = check_database_health()
    redis_ok = check_redis_health()
    
    # Report actual status
    if db_ok and redis_ok:
        print("✅ All database services healthy")
        exit_code = 0
    elif db_ok and not redis_ok:
        print("⚠️ Database healthy, Redis connection issues")
        exit_code = 1
    elif not db_ok and redis_ok:
        print("⚠️ Redis healthy, Database connection issues") 
        exit_code = 1
    else:
        print("⚠️ Both Database and Redis connection issues")
        exit_code = 1
    
    # Allow override for CI environments via environment variable
    if os.getenv("CI_NON_BLOCKING_DB_CHECKS", "false").lower() == "true":
        print("📝 CI mode: treating as non-blocking (exit 0)")
        exit_code = 0
    
    sys.exit(exit_code)