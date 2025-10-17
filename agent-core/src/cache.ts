interface CacheEntry<T> {
  value: T;
  timestamp: number;
}

const cache = new Map<string, CacheEntry<any>>();

export function get<T>(key: string, ttl: number = 3600): T | undefined {
  const entry = cache.get(key);
  if (!entry) return undefined;
  
  if (Date.now() - entry.timestamp > ttl * 1000) {
    cache.delete(key);
    return undefined;
  }
  
  return entry.value;
}

export function set<T>(key: string, value: T): void {
  cache.set(key, {
    value,
    timestamp: Date.now()
  });
}

export function clear(): void {
  cache.clear();
}

export function size(): number {
  return cache.size;
}

export function cleanup(maxAge: number = 3600): number {
  const now = Date.now();
  let removed = 0;
  
  for (const [key, entry] of cache.entries()) {
    if (now - entry.timestamp > maxAge * 1000) {
      cache.delete(key);
      removed++;
    }
  }
  
  return removed;
}