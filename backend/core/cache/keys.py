from __future__ import annotations

# Single place for cache key construction
def plan_key(plan_id: str) -> str:
    return f"plan:{plan_id}"

def plan_steps_key(plan_id: str) -> str:
    return f"plan:{plan_id}:steps"

def user_key(sub: str, org_key: str) -> str:
    return f"user:{org_key}:{sub}"

def role_key(sub: str, org_key: str) -> str:
    return f"role:{org_key}:{sub}"

def org_key_val(org_key: str) -> str:
    return f"org:{org_key}"

def generic(bucket: str, *parts: str) -> str:
    return ":".join([bucket, *parts])