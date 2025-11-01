from __future__ import annotations


async def on_startup():
    # place for warmups (e.g., compile regex, prime caches) if needed
    return


async def on_shutdown():
    # graceful close of redis if used
    try:
        from infra.cache.redis_cache import cache

        r = getattr(cache, "_r", None)
        if r:
            await r.close()
    except Exception:
        pass
