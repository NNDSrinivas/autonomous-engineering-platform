// A resilient SSE client with auto-resume and demultiplexing support
// Usage: const sse = new SSEClient(tokenGetter); sse.subscribe(planId, handler)

import { CORE_API } from '../../api/client';

export type EventHandler = (evt: { planId: string; type: string; seq?: number; payload: any }) => void;
export type TokenGetter = () => string | null;

// Type guard for experimental Scheduler API (Chrome 94+, not widely supported)
interface SchedulerAPI {
  yield: () => Promise<void>;
}

function hasSchedulerYield(obj: any): obj is { scheduler: SchedulerAPI } {
  return 'scheduler' in obj && 
         obj.scheduler && 
         typeof obj.scheduler.yield === 'function';
}

// Interface for our EventSource polyfill - includes all EventSource properties for compatibility
interface EventSourcePolyfill {
  readonly CONNECTING: 0;
  readonly OPEN: 1;
  readonly CLOSED: 2;
  readyState: number;
  withCredentials: boolean;
  onopen: ((this: EventSource, ev: Event) => any) | null;
  onmessage: ((this: EventSource, ev: MessageEvent) => any) | null;
  onerror: ((this: EventSource, ev: Event) => any) | null;
  listeners: Map<string, Set<EventListener>>;
  url: string;
  addEventListener(type: string, listener: EventListener): void;
  removeEventListener(type: string, listener: EventListener): void;
  dispatchEvent(event: Event): boolean;
  close(): void;
}

export class SSEClient {
  private static readonly MAX_RECONNECT_DELAY = 30000; // 30 seconds
  private static readonly BASE_DELAY = 1000; // 1 second  
  private static readonly JITTER_MS = 250; // 250ms jitter
  private static readonly MAX_BACKOFF_MULTIPLIER = 30; // Cap exponential backoff to prevent overflow
  
  // SSE protocol field prefix lengths (for efficient parsing)
  private static readonly SSE_EVENT_PREFIX_LENGTH = 6; // length of "event:"
  private static readonly SSE_DATA_PREFIX_LENGTH = 5; // length of "data:"
  private static readonly SSE_DATA_SPACE_PREFIX_LENGTH = 6; // length of "data: "
  private static readonly SSE_ID_PREFIX_LENGTH = 3; // length of "id:"
  
  // Allowed SSE event types for security validation
  private static readonly ALLOWED_EVENT_TYPES = new Set(["note", "step", "cursor", "presence", "message"]);
  
  /**
   * Extract data content from SSE data line, handling both "data:" and "data: " prefixes
   */
  private static extractDataContent(line: string): string {
    return line.substring(line.startsWith('data: ') ? 
      SSEClient.SSE_DATA_SPACE_PREFIX_LENGTH : 
      SSEClient.SSE_DATA_PREFIX_LENGTH);
  }
  
  /**
   * Sanitize value for safe logging to prevent log injection attacks
   */
  private static sanitizeForLogging(value: string): string {
    // Remove or replace line-breaking characters to prevent log injection
    const sanitized = value.replace(/[\r\n\u2028\u2029]+/g, ' ');
    // Limit length to prevent log flooding
    return sanitized.length > 100 ? sanitized.substring(0, 97) + '...' : sanitized;
  }
  
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
    // Cap reconnect attempts to prevent overflow in exponential calculation
    const cappedAttempt = Math.min(this.reconnectAttempt, SSEClient.MAX_BACKOFF_MULTIPLIER);
    const exponentialDelay = (2 ** cappedAttempt) * SSEClient.BASE_DELAY;
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
      
      console.warn('Fetch-based EventSource failed, cannot establish SSE connection:', error);
      // Fallback to token-in-URL is disabled for security reasons, even in non-production environments.
      // Please configure proper authentication headers or use a secure local transport for local development.
      throw new Error(
        'Fetch-based EventSource failed. Fallback to token-in-URL is disabled for security reasons. ' +
        'Please configure proper authentication headers or use a secure local transport for local development. ' +
        'Original error: ' + error
      );
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
    
    const eventSource: EventSourcePolyfill = {
      CONNECTING: 0 as const,
      OPEN: 1 as const,
      CLOSED: 2 as const,
      readyState: 0, // CONNECTING
      withCredentials: false,
      onopen: null as ((this: EventSource, ev: Event) => any) | null,
      onmessage: null as ((this: EventSource, ev: MessageEvent) => any) | null,
      onerror: null as ((this: EventSource, ev: Event) => any) | null,
      listeners,
      addEventListener: (type: string, listener: EventListener) => {
        if (!eventSource.listeners.has(type)) {
          eventSource.listeners.set(type, new Set());
        }
        eventSource.listeners.get(type)!.add(listener);
      },
      removeEventListener: (type: string, listener: EventListener) => {
        const typeListeners = eventSource.listeners.get(type);
        if (typeListeners) {
          typeListeners.delete(listener);
          if (typeListeners.size === 0) {
            eventSource.listeners.delete(type);
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
          this.onopen.call(this as unknown as EventSource, event);
        } else if (event.type === 'message' && this.onmessage) {
          this.onmessage.call(this as unknown as EventSource, event as MessageEvent);
        } else if (event.type === 'error' && this.onerror) {
          this.onerror.call(this as unknown as EventSource, event);
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
      let hasOpenedConnection = false;

      // Event variables persist across chunks to handle partial events
      // Note: These variables are declared within the fetch().then() scope, so they are
      // implicitly reset to their initial values on each new connection (reconnection).
      // eventId persists across events within a single connection for Last-Event-ID tracking.
      let eventType = 'message';
      let eventData = '';
      let eventId = '';
      let shouldDropEvent = false; // Track if current event should be dropped due to invalid type

      // Batch processing variables to reduce event loop overhead
      let processedChunks = 0;
      const MAX_CHUNKS_PER_BATCH = 10;

      const processStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              eventSource.dispatchEvent(new Event('error'));
              break;
            }

            // Dispatch 'open' event only once after receiving the first successful chunk
            if (!hasOpenedConnection) {
              hasOpenedConnection = true;
              eventSource.readyState = 1; // OPEN
              eventSource.dispatchEvent(new Event('open'));
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
              if (line.startsWith('event:')) {
                const extractedEventType = line.substring(SSEClient.SSE_EVENT_PREFIX_LENGTH).trim();
                // Validate event type against whitelist to prevent injection attacks
                if (SSEClient.ALLOWED_EVENT_TYPES.has(extractedEventType)) {
                  eventType = extractedEventType;
                  shouldDropEvent = false;
                } else {
                  console.warn('SSE: Dropping event with unknown type:', SSEClient.sanitizeForLogging(extractedEventType));
                  shouldDropEvent = true;
                }
              } else if (line.startsWith('data:')) {
                eventData += SSEClient.extractDataContent(line) + '\n';
              } else if (line.startsWith('id:')) {
                eventId = line.substring(SSEClient.SSE_ID_PREFIX_LENGTH).trim();
              } else if (line === '') {
                // Empty line signals end of event
                if (eventData && !shouldDropEvent) {
                  const messageEvent = new MessageEvent(eventType, {
                    data: eventData.slice(0, -1), // Remove trailing newline
                    lastEventId: eventId,
                  });
                  eventSource.dispatchEvent(messageEvent);
                }
                // Reset event variables after processing (whether dispatched or dropped)
                eventData = '';
                eventType = 'message';
                shouldDropEvent = false;
                // eventId is intentionally NOT reset here to preserve Last-Event-ID tracking.
                // eventId persists across events within the same connection and is only reset on reconnection.
              }
            }

            // Yield control periodically to prevent blocking the main thread
            processedChunks++;
            if (processedChunks >= MAX_CHUNKS_PER_BATCH) {
              processedChunks = 0;
              // Yield using the most efficient available method with fallbacks
              // Feature detection for experimental scheduler.yield() API (Chrome 94+ only)
              if (hasSchedulerYield(globalThis as any)) {
                await (globalThis as any).scheduler.yield();
              } else if (typeof queueMicrotask === 'function') {
                await new Promise<void>(resolve => queueMicrotask(resolve));
              } else {
                await new Promise<void>(resolve => setTimeout(resolve, 0));
              }
            }
          }
        } catch (error: any) {
          if (error.name !== 'AbortError') {
            eventSource.dispatchEvent(new Event('error'));
          }
        }
      };

      processStream();
    }).catch(error => {
      if (error.name !== 'AbortError') {
        eventSource.dispatchEvent(new Event('error'));
      }
    });

    return eventSource as unknown as EventSource;
  }

  private dispatch(type: string, e: MessageEvent) {
    try {
      const payload = e.data ? JSON.parse(e.data) : {};
      const seq = (e as any).lastEventId ? Number((e as any).lastEventId) : undefined;
      const planId = this.extractPlanId(payload) || this.primaryPlanForURL();
      if (seq && planId) this.lastSeq.set(planId, seq);
      this.handlers.get(planId)?.forEach((fn) => fn({ planId, type, seq, payload }));
    } catch (err) {
      // Log malformed lines for debugging
      console.warn("Malformed SSE message received in SSEClient.dispatch:", { data: e.data, error: err });
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