// A tiny offline outbox for plan mutations. Uses localStorage for persistence.
export type OutboxItem = { 
  id: string; 
  url: string; 
  method: string; 
  headers?: Record<string, string>; 
  body: any; 
  ts: number;
  retryCount: number;
};

export class Outbox {
  private key = "aep.outbox.v1";
  private readonly MAX_RETRIES = 3;
  private readonly MAX_AGE_HOURS = 24;
  private readonly MS_PER_HOUR = 60 * 60 * 1000; // Milliseconds per hour
  private cache: OutboxItem[] | null = null; // Write-through cache

  push(item: Omit<OutboxItem, "ts" | "retryCount">) {
    const list = this.read();
    list.push({ ...item, ts: Date.now(), retryCount: 0 });
    this.write(list);
  }

  async flush(
    fetcher: (url: string, init: RequestInit) => Promise<Response>,
    onDropped?: (item: OutboxItem, reason: 'age' | 'retries' | 'client-error') => void
  ) {
    const list = this.read();
    const keep: OutboxItem[] = [];
    const now = Date.now();
    const maxAge = this.MAX_AGE_HOURS * this.MS_PER_HOUR;
    
    for (const it of list) {
      // Remove items that are too old or have exceeded retry limit
      if ((now - it.ts) > maxAge || it.retryCount >= this.MAX_RETRIES) {
        console.warn(`Outbox: Dropping item after ${it.retryCount} retries or age limit`, { id: it.id, url: it.url });
        onDropped?.(it, (now - it.ts) > maxAge ? 'age' : 'retries');
        continue; // Don't keep this item
      }
      
      try {
        const r = await fetcher(it.url, { 
          method: it.method, 
          headers: { 
            "Content-Type": "application/json",
            ...(it.headers || {})
          }, 
          body: JSON.stringify(it.body) 
        });
        if (!r.ok) {
          // Only retry server errors (5xx) - client errors (4xx) will never succeed
          if (r.status >= 500 && r.status < 600) {
            keep.push({ ...it, retryCount: it.retryCount + 1 });
          } else if (r.status >= 400 && r.status < 500) {
            // Log dropped 4xx errors for user visibility
            console.warn(`Outbox: Dropping item due to client error ${r.status}:`, {
              url: it.url,
              method: it.method,
              status: r.status,
              timestamp: new Date(it.ts).toISOString()
            });
            onDropped?.(it, 'client-error');
          }
        }
        // If r.ok, don't add to keep (successfully processed)
      } catch {
        // Increment retry count and keep for retry
        keep.push({ ...it, retryCount: it.retryCount + 1 });
      }
    }
    this.write(keep);
    
    // Return number of items successfully processed
    return list.length - keep.length;
  }

  count(): number {
    return this.read().length;
  }

  clear() {
    this.write([]);
  }

  private read(): OutboxItem[] {
    // Return cached data if available
    if (this.cache !== null) {
      return this.cache;
    }
    
    try {
      const items = JSON.parse(localStorage.getItem(this.key) || "[]");
      // Handle backwards compatibility: add retryCount to existing items
      const processedItems = items.map((item: any) => ({
        ...item,
        retryCount: item.retryCount ?? 0
      }));
      this.cache = processedItems;
      return processedItems;
    } catch {
      const emptyList: OutboxItem[] = [];
      this.cache = emptyList;
      return emptyList;
    }
  }

  private write(list: OutboxItem[]) {
    this.cache = list; // Update cache first
    try {
      localStorage.setItem(this.key, JSON.stringify(list));
    } catch {
      // localStorage might be full or unavailable
    }
  }
}