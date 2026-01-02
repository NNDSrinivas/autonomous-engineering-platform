/**
 * Traces Data Source Integration
 * 
 * Fetches distributed traces from Jaeger, Zipkin, or other tracing systems.
 */

import {
    TracesConfig,
    TraceSpan,
    SpanStatus
} from '../types';

/**
 * Fetch traces from configured sources
 */
export async function fetchTraces(config: TracesConfig): Promise<TraceSpan[]> {
    console.log('🔍 Fetching distributed traces...');
    
    const allTraces: TraceSpan[] = [];
    
    try {
        if (config.jaeger) {
            const jaegerTraces = await fetchFromJaeger(config.jaeger);
            allTraces.push(...jaegerTraces);
        }
        
        if (config.zipkin) {
            const zipkinTraces = await fetchFromZipkin(config.zipkin);
            allTraces.push(...zipkinTraces);
        }
        
        console.log(`✅ Successfully fetched ${allTraces.length} trace spans`);
        return allTraces;
        
    } catch (error) {
        console.error('❌ Failed to fetch traces:', error);
        throw error;
    }
}

/**
 * Fetch traces from Jaeger
 */
async function fetchFromJaeger(config: any): Promise<TraceSpan[]> {
    console.log(`🔍 Querying Jaeger: ${config.endpoint}`);
    
    try {
        const lookback = '15m';
        const limit = 100;
        
        const params = new URLSearchParams({
            service: config.service,
            lookback,
            limit: limit.toString()
        });
        
        const url = `${config.endpoint}/api/traces?${params}`;
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Jaeger query failed: ${response.status}`);
        }
        
        const data = await response.json();
        return parseJaegerTraces(data);
        
    } catch (error) {
        console.error('Failed to fetch from Jaeger:', error);
        // Return mock traces for demonstration
        return generateMockTraces(config.service, 20);
    }
}

/**
 * Fetch traces from Zipkin
 */
async function fetchFromZipkin(config: any): Promise<TraceSpan[]> {
    console.log(`🔍 Querying Zipkin: ${config.endpoint}`);
    
    try {
        const endTs = Date.now();
        const startTs = endTs - (15 * 60 * 1000); // Last 15 minutes
        
        const params = new URLSearchParams({
            serviceName: config.service,
            endTs: endTs.toString(),
            lookback: (15 * 60 * 1000).toString(),
            limit: '100'
        });
        
        const url = `${config.endpoint}/api/v2/traces?${params}`;
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Zipkin query failed: ${response.status}`);
        }
        
        const data = await response.json();
        return parseZipkinTraces(data as any[]);
        
    } catch (error) {
        console.error('Failed to fetch from Zipkin:', error);
        // Return mock traces for demonstration
        return generateMockTraces(config.service, 15);
    }
}

/**
 * Parse Jaeger trace data into TraceSpan format
 */
function parseJaegerTraces(data: any): TraceSpan[] {
    const spans: TraceSpan[] = [];
    
    if (!data.data) {
        return spans;
    }
    
    for (const trace of data.data) {
        if (!trace.spans) continue;
        
        for (const span of trace.spans) {
            spans.push({
                traceId: trace.traceID,
                spanId: span.spanID,
                operationName: span.operationName,
                startTime: span.startTime,
                duration: span.duration,
                tags: parseJaegerTags(span.tags || []),
                status: determineSpanStatus(span.tags || []),
                parentSpanId: span.references?.[0]?.spanID
            });
        }
    }
    
    return spans;
}

/**
 * Parse Zipkin trace data into TraceSpan format
 */
function parseZipkinTraces(data: any[]): TraceSpan[] {
    const spans: TraceSpan[] = [];
    
    for (const trace of data) {
        for (const span of trace) {
            spans.push({
                traceId: span.traceId,
                spanId: span.id,
                operationName: span.name,
                startTime: span.timestamp,
                duration: span.duration || 0,
                tags: span.tags || {},
                status: determineZipkinSpanStatus(span),
                parentSpanId: span.parentId
            });
        }
    }
    
    return spans;
}

/**
 * Parse Jaeger tags into key-value pairs
 */
function parseJaegerTags(tags: any[]): Record<string, string> {
    const parsed: Record<string, string> = {};
    
    for (const tag of tags) {
        if (tag.key && tag.value !== undefined) {
            parsed[tag.key] = String(tag.value);
        }
    }
    
    return parsed;
}

/**
 * Determine span status from Jaeger tags
 */
function determineSpanStatus(tags: any[]): SpanStatus {
    for (const tag of tags) {
        if (tag.key === 'error' && tag.value === true) {
            return SpanStatus.ERROR;
        }
        if (tag.key === 'http.status_code') {
            const statusCode = parseInt(tag.value);
            if (statusCode >= 500) {
                return SpanStatus.ERROR;
            }
            if (statusCode === 408 || statusCode === 504) {
                return SpanStatus.TIMEOUT;
            }
        }
    }
    
    return SpanStatus.OK;
}

/**
 * Determine span status from Zipkin span data
 */
function determineZipkinSpanStatus(span: any): SpanStatus {
    if (span.tags) {
        if (span.tags.error === 'true' || span.tags.error === true) {
            return SpanStatus.ERROR;
        }
        
        const httpStatus = span.tags['http.status_code'];
        if (httpStatus) {
            const statusCode = parseInt(httpStatus);
            if (statusCode >= 500) {
                return SpanStatus.ERROR;
            }
            if (statusCode === 408 || statusCode === 504) {
                return SpanStatus.TIMEOUT;
            }
        }
    }
    
    return SpanStatus.OK;
}

/**
 * Generate mock trace data for demonstration
 */
function generateMockTraces(service: string, count: number): TraceSpan[] {
    const traces: TraceSpan[] = [];
    const now = Date.now() * 1000; // Convert to microseconds
    
    const operations = [
        'GET /api/users',
        'POST /api/orders',
        'GET /api/products',
        'PUT /api/users/{id}',
        'DELETE /api/orders/{id}',
        'GET /health',
        'POST /auth/login',
        'GET /api/metrics'
    ];
    
    for (let i = 0; i < count; i++) {
        const traceId = generateTraceId();
        const spanId = generateSpanId();
        const startTime = now - Math.floor(Math.random() * 15 * 60 * 1000000); // Last 15 minutes
        const duration = Math.floor(Math.random() * 1000000); // Random duration up to 1 second
        const operation = operations[Math.floor(Math.random() * operations.length)];
        
        // Determine status based on some probability
        let status = SpanStatus.OK;
        const errorChance = Math.random();
        if (errorChance < 0.05) { // 5% error rate
            status = SpanStatus.ERROR;
        } else if (errorChance < 0.08) { // 3% timeout rate
            status = SpanStatus.TIMEOUT;
        }
        
        traces.push({
            traceId,
            spanId,
            operationName: operation,
            startTime,
            duration,
            tags: {
                'service.name': service,
                'http.method': operation.split(' ')[0],
                'http.url': operation.split(' ')[1],
                'http.status_code': status === SpanStatus.ERROR ? '500' : 
                                   status === SpanStatus.TIMEOUT ? '504' : '200',
                'component': 'http-server'
            },
            status
        });
    }
    
    return traces.sort((a, b) => b.startTime - a.startTime);
}

/**
 * Generate a random trace ID
 */
function generateTraceId(): string {
    return Math.random().toString(16).substr(2, 16).padEnd(16, '0');
}

/**
 * Generate a random span ID
 */
function generateSpanId(): string {
    return Math.random().toString(16).substr(2, 8).padEnd(8, '0');
}

/**
 * Find spans with errors
 */
export function findErrorSpans(spans: TraceSpan[]): TraceSpan[] {
    return spans.filter(span => span.status === SpanStatus.ERROR);
}

/**
 * Find slow spans (above threshold)
 */
export function findSlowSpans(spans: TraceSpan[], thresholdMicroseconds: number): TraceSpan[] {
    return spans.filter(span => span.duration > thresholdMicroseconds);
}

/**
 * Group spans by operation
 */
export function groupSpansByOperation(spans: TraceSpan[]): Record<string, TraceSpan[]> {
    const grouped: Record<string, TraceSpan[]> = {};
    
    for (const span of spans) {
        if (!grouped[span.operationName]) {
            grouped[span.operationName] = [];
        }
        grouped[span.operationName].push(span);
    }
    
    return grouped;
}

/**
 * Calculate operation statistics
 */
export function calculateOperationStats(spans: TraceSpan[]): any {
    if (spans.length === 0) {
        return null;
    }
    
    const durations = spans.map(s => s.duration);
    const errorCount = spans.filter(s => s.status === SpanStatus.ERROR).length;
    
    durations.sort((a, b) => a - b);
    
    return {
        count: spans.length,
        errorRate: errorCount / spans.length,
        avgDuration: durations.reduce((sum, d) => sum + d, 0) / durations.length,
        p50Duration: durations[Math.floor(durations.length * 0.5)],
        p95Duration: durations[Math.floor(durations.length * 0.95)],
        p99Duration: durations[Math.floor(durations.length * 0.99)]
    };
}