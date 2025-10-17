"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.realtimeApi = exports.coreApi = void 0;
const coreApi = () => process.env.AEP_CORE_API || 'http://localhost:8002';
exports.coreApi = coreApi;
const realtimeApi = () => process.env.AEP_REALTIME_API || 'http://localhost:8001';
exports.realtimeApi = realtimeApi;
