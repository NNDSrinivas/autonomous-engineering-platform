/**
 * Extensions API client
 * Provides methods for interacting with the Phase 7.0 Extension Platform
 */

import { api } from './client';

export interface ExtensionManifest {
    id: string;
    name: string;
    version: string;
    description: string;
    author: {
        name: string;
        email?: string;
        website?: string;
    };
    category: 'development' | 'productivity' | 'integration' | 'analytics' | 'security' | 'other';
    tags: string[];
    icon?: string;
    homepage?: string;
    repository?: string;
    license?: string;
    rating?: number;
    downloadCount?: number;
    lastUpdated: string;
    capabilities: Array<{
        name: string;
        description: string;
        input_schema: Record<string, any>;
        output_schema: Record<string, any>;
        examples?: Array<{
            name: string;
            input: Record<string, any>;
            output: Record<string, any>;
        }>;
    }>;
    permissions: string[];
    dependencies?: string[];
    installation?: {
        steps: string[];
        requirements?: string[];
    };
}

export interface InstallationStatus {
    extension_id: string;
    status: 'installing' | 'installed' | 'failed' | 'updating' | 'uninstalling';
    progress?: number;
    error?: string;
    installed_at?: string;
    version?: string;
}

export interface SearchFilters {
    category?: string;
    tags?: string[];
    author?: string;
    rating_min?: number;
    sort?: 'name' | 'rating' | 'downloads' | 'updated' | 'relevance';
    sort_order?: 'asc' | 'desc';
}

export interface SearchRequest {
    query?: string;
    filters?: SearchFilters;
    page?: number;
    page_size?: number;
}

export interface ExtensionExecuteRequest {
    capability_name: string;
    input_data: Record<string, any>;
}

export interface ExtensionExecuteResponse {
    success: boolean;
    output: Record<string, any>;
    execution_time: number;
    error?: string;
}

export interface ValidationResult {
    valid: boolean;
    errors: string[];
    warnings: string[];
    security_score?: number;
}

class ExtensionsAPI {
    // Marketplace browsing
    async getFeaturedExtensions(): Promise<ExtensionManifest[]> {
        const response = await api.get('/api/extensions/marketplace/featured');
        return response.data;
    }

    async searchMarketplace(request: SearchRequest): Promise<{
        extensions: ExtensionManifest[];
        total: number;
        page: number;
        pages: number;
    }> {
        const response = await api.post('/api/extensions/marketplace/search', request);
        return response.data;
    }

    async getExtensionDetails(extensionId: string): Promise<ExtensionManifest> {
        const response = await api.get(`/api/extensions/marketplace/${extensionId}`);
        return response.data;
    }

    // Installation management
    async installExtension(extensionId: string, version?: string): Promise<{
        success: boolean;
        installation_id: string;
        message: string;
    }> {
        const response = await api.post('/api/extensions/install', {
            extension_id: extensionId,
            version
        });
        return response.data;
    }

    async getInstallationStatus(installationId: string): Promise<InstallationStatus> {
        const response = await api.get(`/api/extensions/install/${installationId}/status`);
        return response.data;
    }

    async getInstalledExtensions(): Promise<ExtensionManifest[]> {
        const response = await api.get('/api/extensions/installed');
        return response.data;
    }

    async uninstallExtension(extensionId: string): Promise<{
        success: boolean;
        message: string;
    }> {
        const response = await api.delete(`/api/extensions/installed/${extensionId}`);
        return response.data;
    }

    async updateExtension(extensionId: string, version?: string): Promise<{
        success: boolean;
        message: string;
    }> {
        const response = await api.put(`/api/extensions/installed/${extensionId}`, {
            version
        });
        return response.data;
    }

    // Extension execution
    async executeCapability(
        extensionId: string,
        request: ExtensionExecuteRequest
    ): Promise<ExtensionExecuteResponse> {
        const response = await api.post(
            `/api/extensions/execute/${extensionId}`,
            request
        );
        return response.data;
    }

    // Extension development and validation
    async validateExtension(manifest: ExtensionManifest): Promise<ValidationResult> {
        const response = await api.post('/api/extensions/validate', manifest);
        return response.data;
    }

    async getCategories(): Promise<Array<{
        id: string;
        name: string;
        description: string;
        count: number;
    }>> {
        const response = await api.get('/api/extensions/categories');
        return response.data;
    }

    async getTags(): Promise<Array<{
        name: string;
        count: number;
    }>> {
        const response = await api.get('/api/extensions/tags');
        return response.data;
    }
}

export const extensionsAPI = new ExtensionsAPI();