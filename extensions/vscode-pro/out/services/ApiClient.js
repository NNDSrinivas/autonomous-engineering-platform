"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiClient = void 0;
const axios_1 = __importDefault(require("axios"));
class ApiClient {
    constructor(authService) {
        this.authService = authService;
        this._baseUrl = 'http://localhost:8001';
    }
    async chat(request) {
        const token = this.authService.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }
        try {
            const response = await axios_1.default.post(`${this._baseUrl}/api/chat`, {
                message: request.message,
                session_id: request.sessionId,
                context: request.context
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });
            return response.data;
        }
        catch (error) {
            if (error.response?.status === 401) {
                // Token expired, sign out
                await this.authService.signOut();
                throw new Error('Session expired. Please sign in again.');
            }
            throw new Error(error.response?.data?.message || error.message || 'Request failed');
        }
    }
    async approveStep(stepId) {
        await this.makeAuthenticatedRequest('POST', `/api/plan/approve/${stepId}`);
    }
    async rejectStep(stepId, reason) {
        await this.makeAuthenticatedRequest('POST', `/api/plan/reject/${stepId}`, { reason });
    }
    async getCurrentPlan() {
        return this.makeAuthenticatedRequest('GET', '/api/plan/current');
    }
    async makeAuthenticatedRequest(method, endpoint, data) {
        const token = this.authService.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }
        try {
            const response = await (0, axios_1.default)({
                method,
                url: `${this._baseUrl}${endpoint}`,
                data,
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });
            return response.data;
        }
        catch (error) {
            if (error.response?.status === 401) {
                await this.authService.signOut();
                throw new Error('Session expired. Please sign in again.');
            }
            throw new Error(error.response?.data?.message || error.message || 'Request failed');
        }
    }
}
exports.ApiClient = ApiClient;
//# sourceMappingURL=ApiClient.js.map