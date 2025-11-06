"use strict";
/**
 * HTTP utilities for VS Code extension
 * Uses Node.js built-in modules for compatibility with Node.js 16+
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.makeHttpRequest = makeHttpRequest;
exports.compatibleFetch = compatibleFetch;
const https = __importStar(require("https"));
const http = __importStar(require("http"));
const url_1 = require("url");
/**
 * Make HTTP request using Node.js built-in modules (compatible with Node.js 16+)
 */
function makeHttpRequest(url, options = {}) {
    return new Promise((resolve, reject) => {
        const parsedUrl = new url_1.URL(url);
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
                        }
                        catch (error) {
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
function compatibleFetch(url, init) {
    return makeHttpRequest(url, init || {});
}
//# sourceMappingURL=http.js.map