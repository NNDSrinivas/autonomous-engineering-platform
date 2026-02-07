/**
 * Frontend Telemetry Service
 *
 * Batches and sends telemetry events to the backend /api/telemetry endpoint.
 * Handles periodic flushing, error recovery, and automatic retries.
 */

export interface TelemetryEvent {
  type: string;
  timestamp: number;
  data: Record<string, any>;
  sessionId?: string;
  userId?: string;
  workspaceRoot?: string;
}

export interface TelemetryBatch {
  events: TelemetryEvent[];
  batchId: string;
  timestamp: number;
}

export interface TelemetryConfig {
  /** Backend base URL (default: extracted from vscodeApi) */
  backendUrl?: string;
  /** Max events before auto-flush (default: 100) */
  maxBatchSize?: number;
  /** Flush interval in ms (default: 60000 = 1 minute) */
  flushIntervalMs?: number;
  /** Enable console logging for debugging */
  debug?: boolean;
}

class TelemetryService {
  private events: TelemetryEvent[] = [];
  private sessionId: string;
  private flushTimer: NodeJS.Timeout | null = null;
  private config: Required<TelemetryConfig>;
  private backendUrl: string | null = null;

  constructor(config: TelemetryConfig = {}) {
    this.sessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    this.config = {
      backendUrl: config.backendUrl || '',
      maxBatchSize: config.maxBatchSize || 100,
      flushIntervalMs: config.flushIntervalMs || 60000,
      debug: config.debug || false,
    };

    // Start periodic flush timer
    this.startFlushTimer();

    // Flush on page unload
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this.flushSync();
      });
    }

    this.log('Telemetry service initialized', {
      sessionId: this.sessionId,
      maxBatchSize: this.config.maxBatchSize,
      flushIntervalMs: this.config.flushIntervalMs,
    });
  }

  /**
   * Set the backend URL for telemetry submission
   */
  setBackendUrl(url: string): void {
    this.backendUrl = url;
    this.log('Backend URL set:', url);
  }

  /**
   * Track a telemetry event
   */
  track(type: string, data: Record<string, any> = {}): void {
    const event: TelemetryEvent = {
      type,
      timestamp: Date.now(),
      data,
      sessionId: this.sessionId,
    };

    this.events.push(event);
    this.log('Event tracked:', { type, eventCount: this.events.length });

    // Auto-flush if batch size exceeded
    if (this.events.length >= this.config.maxBatchSize) {
      this.log('Max batch size reached, flushing...');
      this.flush();
    }
  }

  /**
   * Track streaming metrics
   */
  trackStreamingMetrics(metrics: {
    time_to_first_token_ms?: number;
    total_duration_ms?: number;
    total_tokens?: number;
    total_chars?: number;
    tokens_per_second?: number;
    activity_events?: number;
  }): void {
    this.track('navi.streaming.performance', metrics);
  }

  /**
   * Track LLM generation metrics
   */
  trackGeneration(params: {
    model: string;
    provider: string;
    latencyMs: number;
    tokens?: number;
    success: boolean;
    error?: string;
  }): void {
    this.track('navi.llm.generation', params);
  }

  /**
   * Track user interaction
   */
  trackInteraction(action: string, data: Record<string, any> = {}): void {
    this.track('navi.user.interaction', { action, ...data });
  }

  /**
   * Track error
   */
  trackError(error: Error | string, context: Record<string, any> = {}): void {
    this.track('navi.error', {
      error: error instanceof Error ? error.message : error,
      stack: error instanceof Error ? error.stack : undefined,
      ...context,
    });
  }

  /**
   * Flush events to backend asynchronously
   */
  async flush(): Promise<void> {
    if (this.events.length === 0) {
      this.log('No events to flush');
      return;
    }

    if (!this.backendUrl) {
      this.log('Backend URL not set, skipping flush');
      return;
    }

    const batch: TelemetryBatch = {
      events: [...this.events],
      batchId: `batch_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
      timestamp: Date.now(),
    };

    // Clear events immediately to prevent duplicates
    this.events = [];

    this.log('Flushing batch:', {
      batchId: batch.batchId,
      eventCount: batch.events.length,
    });

    try {
      const response = await fetch(`${this.backendUrl}/api/telemetry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(batch),
      });

      if (!response.ok) {
        const error = await response.text();
        console.error('[Telemetry] Failed to submit batch:', error);
        // Don't re-queue events on failure to avoid memory leaks
      } else {
        this.log('Batch submitted successfully:', batch.batchId);
      }
    } catch (error) {
      console.error('[Telemetry] Error submitting batch:', error);
      // Don't re-queue events on failure to avoid memory leaks
    }
  }

  /**
   * Flush events synchronously (for page unload)
   */
  private flushSync(): void {
    if (this.events.length === 0 || !this.backendUrl) {
      return;
    }

    const batch: TelemetryBatch = {
      events: [...this.events],
      batchId: `batch_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
      timestamp: Date.now(),
    };

    this.events = [];

    try {
      // Use sendBeacon for synchronous unload
      if (navigator.sendBeacon) {
        const blob = new Blob([JSON.stringify(batch)], {
          type: 'application/json',
        });
        navigator.sendBeacon(`${this.backendUrl}/api/telemetry`, blob);
        this.log('Batch sent via sendBeacon:', batch.batchId);
      } else {
        // Fallback to synchronous XHR (deprecated but works)
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${this.backendUrl}/api/telemetry`, false); // false = synchronous
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify(batch));
        this.log('Batch sent via XHR:', batch.batchId);
      }
    } catch (error) {
      console.error('[Telemetry] Error in sync flush:', error);
    }
  }

  /**
   * Start periodic flush timer
   */
  private startFlushTimer(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }

    this.flushTimer = setInterval(() => {
      this.log('Periodic flush triggered');
      this.flush();
    }, this.config.flushIntervalMs);
  }

  /**
   * Stop periodic flush timer
   */
  stop(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    this.flush(); // Final flush
    this.log('Telemetry service stopped');
  }

  /**
   * Get current session ID
   */
  getSessionId(): string {
    return this.sessionId;
  }

  /**
   * Get pending event count
   */
  getPendingCount(): number {
    return this.events.length;
  }

  /**
   * Internal logging
   */
  private log(message: string, data?: any): void {
    if (this.config.debug) {
      console.log(`[Telemetry] ${message}`, data || '');
    }
  }
}

// Export singleton instance
export const telemetryService = new TelemetryService({
  debug: false, // Set to true for development
});

export default telemetryService;
