/**
 * HTTP utilities for VS Code extension
 * Uses Node.js built-in modules for compatibility with Node.js 16+
 */

import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';

/**
 * Make HTTP request using Node.js built-in modules (compatible with Node.js 16+)
 */
export function makeHttpRequest(url: string, options: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
} = {}): Promise<{ ok: boolean; status: number; json: () => Promise<any> }> {
    return new Promise((resolve, reject) => {
        const parsedUrl = new URL(url);
        const isHttps = parsedUrl.protocol === 'https:';
        const httpModule = isHttps ? https : http;
        
        const requestOptions = {
            hostname: parsedUrl.hostname,
            port: parsedUrl.port || (isHttps ? 443 : 80),
            path: parsedUrl.pathname + parsedUrl.search,
            method: options.method || 'GET',
            headers: options.headers || {}
        };

        const req = httpModule.request(requestOptions, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                resolve({
                    ok: (res.statusCode || 0) >= 200 && (res.statusCode || 0) < 300,
                    status: res.statusCode || 0,
                    json: () => {
                        try {
                            return Promise.resolve(JSON.parse(data));
                        } catch (error) {
                            const preview = data.length > 100 ? data.substring(0, 100) + '...' : data;
                            return Promise.reject(new Error(`Invalid JSON response: ${error instanceof Error ? error.message : 'Unknown error'}. Response data: ${preview}`));
                        }
                    }
                });
            });
        });

        req.on('error', reject);
        
        if (options.body) {
            req.write(options.body);
        }
        
        req.end();
    });
}

/**
 * Compatibility layer that mimics fetch API but uses Node.js built-in modules
 * This allows us to replace fetch calls with minimal code changes
 */
export function compatibleFetch(url: string, init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
}): Promise<{ ok: boolean; status: number; json: () => Promise<any> }> {
    return makeHttpRequest(url, init || {});
}