/**
 * TypeScript definitions for NAVI Extension API
 */

export interface ExtensionContext {
    project: {
        name: string;
        path: string;
        repoUrl?: string;
    };
    user: {
        id: string;
        name: string;
        permissions: string[];
    };
    ci: {
        provider: 'github' | 'gitlab' | 'jenkins' | 'other';
        apiUrl: string;
        accessToken?: string;
    };
    navi: {
        apiUrl: string;
        version: string;
    };
}

export interface ExtensionResult {
    success: boolean;
    message: string;
    requiresApproval: boolean;
    proposal?: ChangeProposal;
    details?: Record<string, any>;
}

export interface ChangeProposal {
    summary: string;
    changes: FileChange[];
    confidence: number;
    rollback: boolean;
    riskLevel: 'low' | 'medium' | 'high';
}

export interface FileChange {
    filePath: string;
    action: 'create' | 'update' | 'delete';
    content?: string;
    diff?: string;
    reason: string;
}

export interface CIFailure {
    job: string;
    step: string;
    error_message: string;
    log_snippet: string;
    file_path?: string;
    line_number?: number;
    failure_type: string;
    logs: string;
}

export interface FailureAnalysis {
    patterns: string[];
    confidence: number;
    errorType: string;
    context: string[];
    suggestions: string[];
}

export interface FixProposal {
    fixable: boolean;
    summary: string;
    changes: FileChange[];
    confidence: number;
    riskLevel: 'low' | 'medium' | 'high';
}