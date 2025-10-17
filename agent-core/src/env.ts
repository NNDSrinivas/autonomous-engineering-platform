export const coreApi = () => process.env.AEP_CORE_API || 'http://localhost:8002';
export const realtimeApi = () => process.env.AEP_REALTIME_API || 'http://localhost:8001';