// A resilient SSE client with auto-resume and demultiplexing support
// Usage: const sse = new SSEClient(tokenGetter); sse.subscribe(planId, handler)

import { CORE_API } from '../../api/client';

export type EventHandler = (evt: { planId: string; type: string; seq?: number; payload: any }) => void;
export type TokenGetter = () => string | null;

export class SSEClient {
  private static readonly MAX_RECONNECT_DELAY = 30000; // 30 seconds
  private static readonly BASE_DELAY = 1000; // 1 second  
  private static readonly JITTER_MS = 250; // 250ms jitter
  private static readonly MAX_BACKOFF_MULTIPLIER = 30; // Cap exponential backoff to prevent overflow
  
  private source: EventSource | null = null;
  private handlers = new Map<string, Set<EventHandler>>(); // planId -> handlers
  private lastSeq = new Map<string, number>();
  private reconnectAttempt = 0;
  private connecting = false;

  constructor(private tokenGetter: TokenGetter) {}

  /**
   * Calculate exponential backoff delay with jitter.
   * Uses binary exponential backoff capped at MAX_BACKOFF_MULTIPLIER,
   * multiplied by BASE_DELAY, with random jitter to prevent thundering herd.
   */
  private calculateBackoffDelay(): number {
    const exponentialDelay = Math.min(Math.pow(2, this.reconnectAttempt), SSEClient.MAX_BACKOFF_MULTIPLIER) * SSEClient.BASE_DELAY;
    const jitteredDelay = exponentialDelay + Math.random() * SSEClient.JITTER_MS;
    return Math.min(SSEClient.MAX_RECONNECT_DELAY, jitteredDelay);
  }

  subscribe(planId: string, handler: EventHandler) {
    if (!this.handlers.has(planId)) this.handlers.set(planId, new Set());
    this.handlers.get(planId)!.add(handler);
    this.ensureConnected();
    return () => this.handlers.get(planId)?.delete(handler);
  }

  private ensureConnected() {
    if (this.connecting || this.source) return;
    this.connecting = true;

    const token = this.tokenGetter();
    const since = this.computeSinceQuery();
    // CRITICAL SECURITY VULNERABILITY: Token in query parameter
    // ⚠️  MUST BE FIXED BEFORE PRODUCTION DEPLOYMENT ⚠️
    // - Exposed in browser history, server logs, proxy logs, and referrer headers
    // - Visible in network monitoring tools and browser developer tools
    // - Can be inadvertently shared when URLs are copied/logged
    // - Creates audit trail of credentials in multiple system logs
    // TODO: URGENT - Implement one of these solutions immediately:
    //   1. Cookie-based authentication with HttpOnly secure cookies
    //   2. Short-lived stream-specific tokens (5-15 min lifetime)
    //   3. SSE polyfill that supports Authorization headers
    //   4. Server-side session validation with secure session tokens
    const url = `${CORE_API}/api/plan/${this.primaryPlanForURL()}/stream?token=${encodeURIComponent(token ?? "")}${since}`;

    // Native EventSource doesn't support custom headers (including Last-Event-ID)
    // The last event ID is handled via URL parameter 'since' instead
    // For future polyfill support that enables headers, implement here
    
    // Native EventSource can't set headers; we pass token via query.
    // In production, consider implementing token exchange for short-lived stream tokens.
    this.source = new EventSource(url);

    this.source.onopen = () => {
      this.reconnectAttempt = 0;
      this.connecting = false;
      // Dispatch custom event for status updates
      window.dispatchEvent(new CustomEvent("aep-stream-open"));
    };

    this.source.onerror = () => {
      window.dispatchEvent(new CustomEvent("aep-stream-error"));
      this.reconnect();
    };

    this.source.onmessage = (e) => {
      // Default event without explicit type
      this.dispatch("message", e);
    };

    // Demux by event type
    const knownTypes = ["note", "step", "cursor", "presence", "message"] as const;
    knownTypes.forEach((t) => {
      this.source!.addEventListener(t, (e) => this.dispatch(t, e as MessageEvent));
    });
  }

  private dispatch(type: string, e: MessageEvent) {
    try {
      const payload = e.data ? JSON.parse(e.data) : {};
      const seq = (e as any).lastEventId ? Number((e as any).lastEventId) : undefined;
      const planId = this.extractPlanId(payload) || this.primaryPlanForURL();
      if (seq && planId) this.lastSeq.set(planId, seq);
      this.handlers.get(planId)?.forEach((fn) => fn({ planId, type, seq, payload }));
    } catch {
      // ignore malformed lines
    }
  }

  private extractPlanId(payload: any): string | undefined {
    if (!payload) return undefined;
    return payload.plan_id || payload.planId || undefined;
  }

  private computeLastEventId(): number | null {
    // Return the minimum last seq across subscribed plans to avoid gaps on resume
    if (this.lastSeq.size === 0) return null;
    return Math.min(...Array.from(this.lastSeq.values()));
  }

  private computeSinceQuery(): string {
    const last = this.computeLastEventId();
    return last ? `&since=${last}` : "";
  }

  private primaryPlanForURL(): string {
    // For multiplexing, any planId works to open the stream; the server channel is per-plan.
    // If you run one stream per plan, you can simplify by using that ID.
    const first = this.handlers.keys().next().value;
    return first || "default";
  }

  private reconnect() {
    if (this.source) {
      this.source.close();
      this.source = null;
    }
    this.connecting = false;
    const delay = this.calculateBackoffDelay();
    this.reconnectAttempt++;
    setTimeout(() => this.ensureConnected(), delay);
  }

  disconnect() {
    if (this.source) {
      this.source.close();
      this.source = null;
    }
    this.connecting = false;
    this.handlers.clear();
    this.lastSeq.clear();
  }
}