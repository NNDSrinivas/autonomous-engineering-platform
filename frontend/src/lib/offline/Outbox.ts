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

  push(item: Omit<OutboxItem, "ts" | "retryCount">) {
    const list = this.read();
    list.push({ ...item, ts: Date.now(), retryCount: 0 });
    this.write(list);
  }

  async flush(fetcher: (url: string, init: RequestInit) => Promise<Response>) {
    const list = this.read();
    const keep: OutboxItem[] = [];
    const now = Date.now();
    const maxAge = this.MAX_AGE_HOURS * 3600000; // 24 hours in milliseconds
    
    for (const it of list) {
      // Remove items that are too old or have exceeded retry limit
      if ((now - it.ts) > maxAge || it.retryCount >= this.MAX_RETRIES) {
        console.warn(`Outbox: Dropping item after ${it.retryCount} retries or age limit`, { id: it.id, url: it.url });
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
          // Increment retry count and keep for retry
          keep.push({ ...it, retryCount: it.retryCount + 1 });
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
    try {
      const items = JSON.parse(localStorage.getItem(this.key) || "[]");
      // Handle backwards compatibility: add retryCount to existing items
      return items.map((item: any) => ({
        ...item,
        retryCount: item.retryCount ?? 0
      }));
    } catch {
      return [];
    }
  }

  private write(list: OutboxItem[]) {
    try {
      localStorage.setItem(this.key, JSON.stringify(list));
    } catch {
      // localStorage might be full or unavailable
    }
  }
}