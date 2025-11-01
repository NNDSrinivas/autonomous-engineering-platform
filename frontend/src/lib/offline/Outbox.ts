// A tiny offline outbox for plan mutations. Uses localStorage for persistence.
export type OutboxItem = { id: string; url: string; method: string; body: any; ts: number };

export class Outbox {
  private key = "aep.outbox.v1";

  push(item: Omit<OutboxItem, "ts">) {
    const list = this.read();
    list.push({ ...item, ts: Date.now() });
    this.write(list);
  }

  async flush(fetcher: (url: string, init: RequestInit) => Promise<Response>) {
    const list = this.read();
    const keep: OutboxItem[] = [];
    for (const it of list) {
      try {
        const r = await fetcher(it.url, { 
          method: it.method, 
          headers: { "Content-Type": "application/json" }, 
          body: JSON.stringify(it.body) 
        });
        if (!r.ok) keep.push(it); // keep for retry
      } catch {
        keep.push(it);
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
      return JSON.parse(localStorage.getItem(this.key) || "[]");
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