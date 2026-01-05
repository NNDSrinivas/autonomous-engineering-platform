from __future__ import annotations
import os


async def on_startup():
    # Initialize tenant database on startup
    try:
        from ..tenant_database import init_tenant_database

        # Get database URL from environment or use default
        database_url = os.getenv("DATABASE_URL", "sqlite:///./data/aep.db")

        # Create data directory if it doesn't exist
        if database_url.startswith("sqlite:///"):
            db_path = database_url.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        init_tenant_database(database_url)
        print(f"✅ Database initialized: {database_url}")

        # Initialize observability after database is ready
        from ..observability import init_observability

        init_observability()
        print("✅ Observability initialized")

        # Initialize extensions after database is ready
        from ...extensions.runtime import init_extensions

        init_extensions()
        print("✅ Extensions initialized")

    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")

    # place for warmups (e.g., compile regex, prime caches) if needed
    return


async def on_shutdown():
    # graceful close of httpx client
    try:
        from ...api.chat import close_http_client

        await close_http_client()
    except Exception:
        # Ignore httpx client cleanup errors during shutdown - non-critical
        pass

    # graceful close of redis if used
    try:
        from infra.cache.redis_cache import cache

        r = getattr(cache, "_r", None)
        if r:
            await r.close()
    except Exception:
        # Ignore Redis cleanup errors during shutdown - non-critical
        pass
