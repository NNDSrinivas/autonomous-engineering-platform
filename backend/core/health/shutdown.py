from __future__ import annotations


async def on_startup():
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
