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
  
  // SSE protocol field prefix lengths (for efficient parsing)
  private static readonly SSE_EVENT_PREFIX_LENGTH = 6; // length of "event:"
  private static readonly SSE_DATA_PREFIX_LENGTH = 5; // length of "data:"
  private static readonly SSE_DATA_SPACE_PREFIX_LENGTH = 6; // length of "data: "
  
  private source: EventSource | null = null;
  private handlers = new Map<string, Set<EventHandler>>(); // planId -> handlers
  private lastSeq = new Map<string, number>();
  private reconnectAttempt = 0;
  private connecting = false;

  private static getEnvironment(): string {
    if (typeof process !== "undefined" && process.env && process.env.NODE_ENV) {
      return process.env.NODE_ENV;
    } else if (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.MODE) {
      return import.meta.env.MODE;
    } else {
      return "production";
    }
  }

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
    return () => {
      this.handlers.get(planId)?.delete(handler);
      // Clean up empty handler sets and close connection if no active subscriptions
      if (this.handlers.get(planId)?.size === 0) {
        this.handlers.delete(planId);
      }
      if (this.handlers.size === 0) {
        this.disconnect();
      }
    };
  }

  private ensureConnected() {
    if (this.connecting || this.source) return;
    this.connecting = true;

    const token = this.tokenGetter();
    
    // Secure SSE connection using fetch polyfill to support Authorization headers
    // This avoids exposing tokens in URL parameters, browser history, or logs
    const baseUrl = `${CORE_API}/api/plan/${this.primaryPlanForURL()}/stream`;
    const url = this.buildSSEUrl(baseUrl);
    
    // Use fetch-based EventSource polyfill for secure authentication
    this.source = this.createSecureEventSource(url, token);

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

  /**
   * Creates a secure EventSource using fetch polyfill with Authorization header.
   * Falls back to native EventSource with token in URL only in non-production environments.
   */
  private createSecureEventSource(url: string, token: string | null): EventSource {
    // Try to use fetch-based polyfill for secure authentication
    try {
      return this.createFetchBasedEventSource(url, token);
    } catch (error) {
      // Only allow fallback in non-production environments
      const env = SSEClient.getEnvironment();
      
      if (env === "production") {
        console.error('Fetch-based EventSource failed and fallback to insecure token-in-URL is disabled in production:', error);
        throw new Error('Secure SSE connection failed and fallback is not allowed in production.');
      }
      
      console.warn('Fetch-based EventSource failed, falling back to native EventSource with token in URL (non-production only):', error);
      // WARNING: This fallback is strictly for local development and must NEVER be used in production.
      // Passing authentication tokens in URL parameters is a security risk, as URLs may be logged in browser history, server logs, and proxy logs.
      // This code path is only enabled in non-production environments to facilitate local testing.
      const urlWithToken = `${url}?token=${encodeURIComponent(token ?? "")}`;
      return new EventSource(urlWithToken);
    }
  }

  /**
   * Creates EventSource using fetch API for secure header support.
   * This implementation manually handles SSE protocol over fetch.
   */
  private createFetchBasedEventSource(url: string, token: string | null): EventSource {
    const controller = new AbortController();
    
    // Create EventSource-compatible object with proper listener support first
    const listeners = new Map<string, Set<EventListener>>();
    
    const eventSource: any = {
      readyState: 0, // CONNECTING
      onopen: null as ((this: EventSource, ev: Event) => any) | null,
      onmessage: null as ((this: EventSource, ev: MessageEvent) => any) | null,
      onerror: null as ((this: EventSource, ev: Event) => any) | null,
      listeners,
      addEventListener: function(type: string, listener: EventListener) {
        if (!this.listeners.has(type)) {
          this.listeners.set(type, new Set());
        }
        this.listeners.get(type)!.add(listener);
      },
      removeEventListener: function(type: string, listener: EventListener) {
        const typeListeners = this.listeners.get(type);
        if (typeListeners) {
          typeListeners.delete(listener);
          if (typeListeners.size === 0) {
            this.listeners.delete(type);
          }
        }
      },
      dispatchEvent: function(event: Event) {
        // Call registered event listeners first
        const typeListeners = this.listeners.get(event.type);
        if (typeListeners) {
          typeListeners.forEach((listener: EventListener) => {
            listener.call(this, event);
          });
        }
        
        // Also call the specific handler properties for DOM events
        if (event.type === 'open' && this.onopen) {
          this.onopen.call(this, event);
        } else if (event.type === 'message' && this.onmessage) {
          this.onmessage.call(this, event as MessageEvent);
        } else if (event.type === 'error' && this.onerror) {
          this.onerror.call(this, event);
        }

        return true;
      },
      close: function() {
        controller.abort();
        this.readyState = 2; // CLOSED
      },
      url
    };

    // Create a fetch-based EventSource polyfill
    const headers: Record<string, string> = {
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Start the fetch request
    fetch(url, {
      method: 'GET',
      headers,
      signal: controller.signal,
    }).then(response => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      if (!response.body) {
        throw new Error('No response body for SSE stream');
      }

      // Process the stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // Event variables persist across chunks to handle partial events
      let eventType = 'message';
      let eventData = '';
      let eventId = '';

      const processChunk = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            eventSource.dispatchEvent(new Event('error'));
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.substring(SSEClient.SSE_EVENT_PREFIX_LENGTH).trim();
            } else if (line.startsWith('data:')) {
              eventData += line.substring(line.startsWith('data: ') ? 
                SSEClient.SSE_DATA_SPACE_PREFIX_LENGTH : 
                SSEClient.SSE_DATA_PREFIX_LENGTH) + '\n';
            } else if (line.startsWith('id:')) {
              eventId = line.substring(3).trim();
            } else if (line === '') {
              // Empty line signals end of event
              if (eventData) {
                const messageEvent = new MessageEvent(eventType, {
                  data: eventData.slice(0, -1), // Remove trailing newline
                  lastEventId: eventId,
                });
                eventSource.dispatchEvent(messageEvent);
                // Reset event variables after dispatching
                eventData = '';
                eventType = 'message';
                eventId = '';
              }
            }
          }

          processChunk();
        }).catch(error => {
          if (error.name !== 'AbortError') {
            eventSource.dispatchEvent(new Event('error'));
          }
        });
      };

      processChunk();
    }).catch(error => {
      if (error.name !== 'AbortError') {
        eventSource.dispatchEvent(new Event('error'));
      }
    });

    // Simulate connection opening
    setTimeout(() => {
      eventSource.readyState = 1; // OPEN
      eventSource.dispatchEvent(new Event('open'));
    }, 0);

    return eventSource as EventSource;
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

  private buildSSEUrl(baseUrl: string): string {
    const urlObj = new URL(baseUrl, window.location.origin);
    const lastEventId = this.computeLastEventId();
    
    if (lastEventId !== null) {
      urlObj.searchParams.set("since", lastEventId.toString());
    }
    
    return urlObj.toString();
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