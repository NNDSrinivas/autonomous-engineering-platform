/**
 * Extension Marketplace Types - Phase 7.1
 * 
 * Enterprise-grade extension marketplace with security, trust, and permissions
 */

export type TrustLevel =
    | "CORE"
    | "VERIFIED"
    | "ORG_APPROVED"
    | "UNTRUSTED";

export type ExtensionCategory =
    | "intelligence"
    | "automation"
    | "security"
    | "infrastructure"
    | "productivity"
    | "integration";

export type PermissionType =
    | "FIX_PROBLEMS"
    | "ANALYZE_PROJECT"
    | "CI_ACCESS"
    | "DEPLOY"
    | "CLUSTER_READ"
    | "WRITE_FILES"
    | "NETWORK_ACCESS"
    | "EXECUTE_COMMANDS";

export interface ExtensionPermission {
    type: PermissionType;
    description: string;
    riskLevel: "low" | "medium" | "high" | "critical";
}

export interface MarketplaceExtension {
    id: string;
    name: string;
    description: string;
    version: string;
    author: {
        name: string;
        verified: boolean;
        organization?: string;
    };
    category: ExtensionCategory;
    tags: string[];
    permissions: ExtensionPermission[];
    trustLevel: TrustLevel;
    capabilities: string[];
    downloads: number;
    rating: number;
    lastUpdated: string;
    iconUrl?: string;
    homepageUrl?: string;
    repositoryUrl?: string;
    isInstalled?: boolean;
    isEnabled?: boolean;
}

export interface InstallationProgress {
    extensionId: string;
    status: "downloading" | "installing" | "enabling" | "complete" | "failed";
    progress: number;
    error?: string;
}

export interface ExtensionManifest {
    id: string;
    name: string;
    version: string;
    description: string;
    main: string;
    permissions: PermissionType[];
    capabilities: {
        [key: string]: {
            description: string;
            inputSchema: any;
            outputSchema: any;
        };
    };
    trustLevel: TrustLevel;
    signature?: string;
}