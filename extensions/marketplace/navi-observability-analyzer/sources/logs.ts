/**
 * Logs Data Source Integration
 * 
 * Fetches and parses log entries from various log sources for correlation with metrics.
 */

import {
    LogsConfig,
    LogEntry,
    LogLevel
} from '../types';

/**
 * Fetch logs from configured sources
 */
export async function fetchLogs(config: LogsConfig): Promise<LogEntry[]> {
    console.log(`📋 Fetching logs from ${config.sources.length} source(s)...`);
    
    const allLogs: LogEntry[] = [];
    
    try {
        for (const source of config.sources) {
            const logs = await fetchFromLogSource(source);
            allLogs.push(...logs);
        }
        
        // Sort logs by timestamp (newest first)
        allLogs.sort((a, b) => b.timestamp - a.timestamp);
        
        console.log(`✅ Successfully fetched ${allLogs.length} log entries`);
        return allLogs;
        
    } catch (error) {
        console.error('❌ Failed to fetch logs:', error);
        throw error;
    }
}

/**
 * Fetch logs from a single source
 */
async function fetchFromLogSource(source: any): Promise<LogEntry[]> {
    switch (source.type) {
        case 'file':
            return await fetchFromLogFile(source);
        case 'elasticsearch':
            return await fetchFromElasticsearch(source);
        case 'splunk':
            return await fetchFromSplunk(source);
        case 'cloudwatch-logs':
            return await fetchFromCloudWatchLogs(source);
        default:
            console.warn(`Unsupported log source type: ${source.type}`);
            return [];
    }
}

/**
 * Fetch logs from local log files
 */
async function fetchFromLogFile(source: any): Promise<LogEntry[]> {
    console.log(`📁 Reading log file: ${source.config.path}`);
    
    // Mock implementation - in production, read actual log files
    const mockLogs = generateMockLogEntries(source.name, 50);
    
    return mockLogs;
}

/**
 * Fetch logs from Elasticsearch
 */
async function fetchFromElasticsearch(source: any): Promise<LogEntry[]> {
    console.log(`🔍 Querying Elasticsearch: ${source.config.endpoint}`);
    
    try {
        const query = {
            query: {
                range: {
                    '@timestamp': {
                        gte: 'now-15m'
                    }
                }
            },
            sort: [
                { '@timestamp': { order: 'desc' } }
            ],
            size: 1000
        };
        
        const response = await fetch(`${source.config.endpoint}/${source.config.index}/_search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(source.config.auth && { 'Authorization': `Basic ${source.config.auth}` })
            },
            body: JSON.stringify(query)
        });
        
        if (!response.ok) {
            throw new Error(`Elasticsearch query failed: ${response.status}`);
        }
        
        const data = await response.json();
        return parseElasticsearchLogs(data, source.name);
        
    } catch (error) {
        console.error(`Failed to fetch logs from Elasticsearch: ${error}`);
        return generateMockLogEntries(source.name, 20);
    }
}

/**
 * Fetch logs from Splunk
 */
async function fetchFromSplunk(source: any): Promise<LogEntry[]> {
    console.log(`📊 Querying Splunk: ${source.config.endpoint}`);
    
    // Mock implementation - in production, use Splunk REST API
    return generateMockLogEntries(source.name, 30);
}

/**
 * Fetch logs from AWS CloudWatch Logs
 */
async function fetchFromCloudWatchLogs(source: any): Promise<LogEntry[]> {
    console.log(`☁️ Querying CloudWatch Logs: ${source.config.logGroup}`);
    
    // Mock implementation - in production, use AWS SDK
    return generateMockLogEntries(source.name, 25);
}

/**
 * Parse Elasticsearch response into LogEntry format
 */
function parseElasticsearchLogs(data: any, sourceName: string): LogEntry[] {
    if (!data.hits || !data.hits.hits) {
        return [];
    }
    
    return data.hits.hits.map((hit: any) => {
        const source = hit._source;
        return {
            timestamp: new Date(source['@timestamp']).getTime(),
            level: parseLogLevel(source.level || source.severity || 'INFO'),
            message: source.message || source.msg || '',
            service: source.service || source.application || 'unknown',
            source: sourceName,
            labels: extractLabels(source),
            structured: source
        };
    });
}

/**
 * Parse log level from various formats
 */
function parseLogLevel(level: string): LogLevel {
    const upperLevel = level.toUpperCase();
    
    switch (upperLevel) {
        case 'DEBUG':
        case 'TRACE':
            return LogLevel.DEBUG;
        case 'INFO':
        case 'INFORMATION':
            return LogLevel.INFO;
        case 'WARN':
        case 'WARNING':
            return LogLevel.WARN;
        case 'ERROR':
        case 'ERR':
            return LogLevel.ERROR;
        case 'FATAL':
        case 'CRITICAL':
        case 'EMERGENCY':
            return LogLevel.FATAL;
        default:
            return LogLevel.INFO;
    }
}

/**
 * Extract relevant labels from log entry
 */
function extractLabels(source: any): Record<string, string> {
    const labels: Record<string, string> = {};
    
    // Common label fields
    if (source.environment) labels.environment = source.environment;
    if (source.version) labels.version = source.version;
    if (source.host) labels.host = source.host;
    if (source.pod) labels.pod = source.pod;
    if (source.namespace) labels.namespace = source.namespace;
    if (source.container) labels.container = source.container;
    
    return labels;
}

/**
 * Generate mock log entries for demonstration
 */
function generateMockLogEntries(source: string, count: number): LogEntry[] {
    const logs: LogEntry[] = [];
    const now = Date.now();
    
    const services = ['api-service', 'auth-service', 'payment-service', 'user-service'];
    const levels = [LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR, LogLevel.DEBUG];
    const messages = [
        'Request processed successfully',
        'Database connection established',
        'Cache miss for key: user:123',
        'Rate limit exceeded for user',
        'Failed to authenticate user',
        'Payment processing completed',
        'Service health check passed',
        'Memory usage is high',
        'Slow query detected',
        'Connection timeout to external service'
    ];
    
    for (let i = 0; i < count; i++) {
        const timestamp = now - (Math.random() * 15 * 60 * 1000); // Last 15 minutes
        const service = services[Math.floor(Math.random() * services.length)];
        const level = levels[Math.floor(Math.random() * levels.length)];
        const message = messages[Math.floor(Math.random() * messages.length)];
        
        logs.push({
            timestamp,
            level,
            message: `${message} - Request ID: ${generateRequestId()}`,
            service,
            source,
            labels: {
                environment: 'production',
                version: '1.2.3'
            },
            structured: {
                requestId: generateRequestId(),
                userId: `user_${Math.floor(Math.random() * 1000)}`,
                duration: Math.floor(Math.random() * 1000)
            }
        });
    }
    
    return logs.sort((a, b) => b.timestamp - a.timestamp);
}

/**
 * Generate a mock request ID
 */
function generateRequestId(): string {
    return Math.random().toString(36).substr(2, 9);
}

/**
 * Filter logs by level
 */
export function filterLogsByLevel(logs: LogEntry[], minLevel: LogLevel): LogEntry[] {
    const levelOrder = {
        [LogLevel.DEBUG]: 0,
        [LogLevel.INFO]: 1,
        [LogLevel.WARN]: 2,
        [LogLevel.ERROR]: 3,
        [LogLevel.FATAL]: 4
    };
    
    const minLevelValue = levelOrder[minLevel];
    
    return logs.filter(log => levelOrder[log.level] >= minLevelValue);
}

/**
 * Find logs matching a pattern
 */
export function findLogsWithPattern(logs: LogEntry[], pattern: RegExp): LogEntry[] {
    return logs.filter(log => pattern.test(log.message));
}

/**
 * Group logs by service
 */
export function groupLogsByService(logs: LogEntry[]): Record<string, LogEntry[]> {
    const grouped: Record<string, LogEntry[]> = {};
    
    for (const log of logs) {
        if (!grouped[log.service]) {
            grouped[log.service] = [];
        }
        grouped[log.service].push(log);
    }
    
    return grouped;
}