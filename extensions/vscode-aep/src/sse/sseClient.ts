export interface SSEClientOptions {
  maxRetries?: number;
  retryDelay?: number;
  heartbeatInterval?: number;
  timeout?: number;
}

export interface SSEClientStatus {
  connected: boolean;
  streaming: boolean;
  retryCount: number;
  lastError?: Error;
  lastHeartbeat?: number;
}

export class SSEClient {
  private eventSource?: EventSource;
  private options: Required<SSEClientOptions>;
  private status: SSEClientStatus;
  private heartbeatTimer?: NodeJS.Timeout;
  private retryTimer?: NodeJS.Timeout;
  private onEvent?: (type: string, data: any) => void;
  private url?: string;

  constructor(options: SSEClientOptions = {}) {
    this.options = {
      maxRetries: options.maxRetries ?? 3,
      retryDelay: options.retryDelay ?? 1000,
      heartbeatInterval: options.heartbeatInterval ?? 30000,
      timeout: options.timeout ?? 60000
    };
    
    this.status = {
      connected: false,
      streaming: false,
      retryCount: 0
    };
  }

  start(url: string, onEvent: (type: string, data: any) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      this.url = url;
      this.onEvent = onEvent;
      
      if (this.eventSource) {
        this.eventSource.close();
      }

      this.status.streaming = true;
      this.eventSource = new EventSource(url);

      let connectionTimeout: NodeJS.Timeout | undefined = setTimeout(() => {
        this.handleError(new Error('Connection timeout'));
        reject(new Error('Connection timeout'));
      }, this.options.timeout);

      this.eventSource.onopen = () => {
        if (connectionTimeout) {
          clearTimeout(connectionTimeout);
          connectionTimeout = undefined;
        }
        
        this.status.connected = true;
        this.status.retryCount = 0;
        this.status.lastError = undefined;
        this.status.lastHeartbeat = Date.now();
        
        this.startHeartbeat();
        onEvent('connected', { connected: true });
        resolve();
      };

      this.eventSource.onmessage = (event) => {
        this.status.lastHeartbeat = Date.now();
        onEvent('message', this.parseEventData(event.data));
      };

      // Enhanced event listeners for all supported event types
      this.eventSource.addEventListener('live-progress', (e: any) => {
        this.status.lastHeartbeat = Date.now();
        onEvent('live-progress', this.parseEventData(e.data));
      });

      this.eventSource.addEventListener('review-entry', (e: any) => {
        this.status.lastHeartbeat = Date.now();
        onEvent('review-entry', this.parseEventData(e.data));
      });

      this.eventSource.addEventListener('done', (e: any) => {
        this.status.lastHeartbeat = Date.now();
        this.status.streaming = false;
        onEvent('done', this.parseEventData(e.data));
      });

      this.eventSource.addEventListener('error', (e: any) => {
        onEvent('stream-error', this.parseEventData(e.data));
      });

      this.eventSource.addEventListener('heartbeat', (e: any) => {
        this.status.lastHeartbeat = Date.now();
        onEvent('heartbeat', { timestamp: Date.now() });
      });

      this.eventSource.addEventListener('prompt_request', (e: any) => {
        this.status.lastHeartbeat = Date.now();
        onEvent('prompt_request', this.parseEventData(e.data));
      });

      this.eventSource.onerror = (error) => {
        if (connectionTimeout) {
          clearTimeout(connectionTimeout);
          connectionTimeout = undefined;
        }
        
        this.handleError(error instanceof Error ? error : new Error('EventSource error'));
        
        // If this is the initial connection attempt, reject the promise
        if (this.status.retryCount === 0 && !this.status.connected) {
          reject(error);
        }
      };
    });
  }

  private parseEventData(data: string): any {
    try {
      return JSON.parse(data);
    } catch (e) {
      return data;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      const now = Date.now();
      const timeSinceLastHeartbeat = now - (this.status.lastHeartbeat || 0);
      
      if (timeSinceLastHeartbeat > this.options.heartbeatInterval * 2) {
        this.handleError(new Error('Heartbeat timeout - connection may be lost'));
      }
    }, this.options.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  private handleError(error: Error): void {
    this.status.lastError = error;
    this.status.connected = false;
    
    if (this.onEvent) {
      this.onEvent('error', {
        message: error.message,
        code: this.getErrorCode(error),
        timestamp: Date.now(),
        canRetry: this.status.retryCount < this.options.maxRetries
      });
    }
    
    // Auto-retry logic
    if (this.status.retryCount < this.options.maxRetries && this.url && this.onEvent) {
      this.scheduleRetry();
    } else {
      this.status.streaming = false;
    }
  }

  private scheduleRetry(): void {
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
    }
    
    const delay = this.options.retryDelay * Math.pow(2, this.status.retryCount);
    this.status.retryCount++;
    
    this.retryTimer = setTimeout(() => {
      if (this.url && this.onEvent) {
        if (this.onEvent) {
          this.onEvent('retry', { 
            attempt: this.status.retryCount, 
            delay, 
            maxRetries: this.options.maxRetries 
          });
        }
        this.start(this.url, this.onEvent).catch(() => {
          // Retry failed, error handling already done in start()
        });
      }
    }, delay);
  }

  private getErrorCode(error: Error): string {
    if (error.message.includes('timeout')) return 'TIMEOUT';
    if (error.message.includes('heartbeat')) return 'HEARTBEAT_TIMEOUT';
    if (error.message.includes('network')) return 'NETWORK_ERROR';
    return 'UNKNOWN';
  }

  retry(): void {
    if (this.url && this.onEvent) {
      this.status.retryCount = 0; // Reset retry count for manual retry
      this.start(this.url, this.onEvent).catch(error => {
        if (this.onEvent) {
          this.onEvent('error', {
            message: error.message,
            code: 'MANUAL_RETRY_FAILED',
            timestamp: Date.now(),
            canRetry: false
          });
        }
      });
    }
  }

  stop(): void {
    this.status.streaming = false;
    this.status.connected = false;
    
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = undefined;
    }
    
    this.stopHeartbeat();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = undefined;
    }
    
    if (this.onEvent) {
      this.onEvent('disconnected', { timestamp: Date.now() });
    }
  }

  getStatus(): SSEClientStatus {
    return { ...this.status };
  }

  isConnected(): boolean {
    return this.status.connected;
  }

  isStreaming(): boolean {
    return this.status.streaming;
  }
}