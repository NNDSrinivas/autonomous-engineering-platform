import axios from 'axios';
import { AuthService } from './AuthService';

export interface ChatRequest {
    message: string;
    sessionId: string;
    context?: {
        workspace?: string;
        activeFile?: string;
        language?: string;
        selection?: any;
    };
}

export interface ChatResponse {
    content: string;
    metadata?: {
        actions?: Array<{
            type: 'file' | 'diff' | 'approve' | 'reject';
            label: string;
            data?: any;
        }>;
        thinking?: boolean;
    };
}

export class ApiClient {
    private _baseUrl: string;

    constructor(private authService: AuthService) {
        this._baseUrl = 'http://localhost:8001';
    }

    public async chat(request: ChatRequest): Promise<ChatResponse> {
        const token = this.authService.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        try {
            const response = await axios.post(`${this._baseUrl}/api/chat`, {
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
        } catch (error: any) {
            if (error.response?.status === 401) {
                // Token expired, sign out
                await this.authService.signOut();
                throw new Error('Session expired. Please sign in again.');
            }
            throw new Error(error.response?.data?.message || error.message || 'Request failed');
        }
    }

    public async approveStep(stepId: string): Promise<void> {
        await this.makeAuthenticatedRequest('POST', `/api/plan/approve/${stepId}`);
    }

    public async rejectStep(stepId: string, reason?: string): Promise<void> {
        await this.makeAuthenticatedRequest('POST', `/api/plan/reject/${stepId}`, { reason });
    }

    public async getCurrentPlan(): Promise<any> {
        return this.makeAuthenticatedRequest('GET', '/api/plan/current');
    }

    private async makeAuthenticatedRequest(method: string, endpoint: string, data?: any): Promise<any> {
        const token = this.authService.getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        try {
            const response = await axios({
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
        } catch (error: any) {
            if (error.response?.status === 401) {
                await this.authService.signOut();
                throw new Error('Session expired. Please sign in again.');
            }
            throw new Error(error.response?.data?.message || error.message || 'Request failed');
        }
    }
}